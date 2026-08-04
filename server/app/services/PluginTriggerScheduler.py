import asyncio
import json
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger

from server.app.db.base import MySQLBaseDAO
from server.app.services.PluginRemoteControlService import PluginRemoteControlService


class PluginTriggerScheduler:
    """Schedules plugin remote-control rules on the server.

    The scheduler only decides when a rule is due. Actual dispatch still uses
    PluginRemoteControlService.create_batch so manual and automatic runs share
    the same WebSocket path and task-log tables.
    """

    def __init__(self, plugin_service: PluginRemoteControlService):
        self.plugin_service = plugin_service
        self.rule_dao = MySQLBaseDAO("fp_plugin_trigger_rule")
        self.log_dao = MySQLBaseDAO("fp_plugin_trigger_log")
        self.client_dao = MySQLBaseDAO("fp_spider_client")
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.interval_seconds = 60
        self._running_rules: set[int] = set()

    async def start(self):
        if self.running:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())
        logger.info("Plugin trigger scheduler started")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
        logger.info("Plugin trigger scheduler stopped")

    async def _loop(self):
        try:
            while self.running:
                try:
                    await self.check_once()
                except Exception as exc:
                    logger.exception(f"Plugin trigger scheduler check failed: {exc}")
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            pass

    async def check_once(self):
        rules = await self.rule_dao.fetch_all(
            "SELECT * FROM fp_plugin_trigger_rule WHERE status = 1 ORDER BY id ASC"
        )
        now = datetime.now()
        for rule in rules:
            rule_id = int(rule["id"])
            if rule_id in self._running_rules:
                continue
            due, source, reason = self._is_due(rule, now)
            if not due:
                if reason:
                    await self._update_next_time(rule, now)
                continue
            self._running_rules.add(rule_id)
            try:
                await self._trigger_rule(rule, source, now)
            finally:
                self._running_rules.discard(rule_id)

    def _is_due(self, rule: Dict[str, Any], now: datetime) -> tuple[bool, str, str]:
        trigger_type = str(rule.get("trigger_type") or "")
        schedule = self._decode_json(rule.get("schedule_json"))
        condition = self._decode_json(rule.get("condition_json"))
        last = self._to_datetime(rule.get("last_trigger_time"))

        if trigger_type == "interval_window":
            return self._interval_window_due(schedule, last, now)
        if trigger_type == "fixed_time":
            return self._fixed_time_due(schedule, last, now)
        if trigger_type == "monthly":
            return self._monthly_due(schedule, last, now)
        if trigger_type == "condition":
            return self._condition_due(condition, last, now)
        return False, trigger_type, "unknown trigger type"

    def _interval_window_due(
        self, schedule: Dict[str, Any], last: Optional[datetime], now: datetime
    ) -> tuple[bool, str, str]:
        if not self._day_allowed(schedule, now):
            return False, "interval_window", ""
        start = self._parse_time(schedule.get("start_time") or "09:00")
        end = self._parse_time(schedule.get("end_time") or "19:00")
        current = now.time().replace(second=0, microsecond=0)
        if not self._time_in_window(current, start, end):
            return False, "interval_window", "outside window"
        interval = max(1, int(schedule.get("interval_minutes") or 5))
        if last and now - last < timedelta(minutes=interval):
            return False, "interval_window", ""
        return True, "interval_window", ""

    def _fixed_time_due(
        self, schedule: Dict[str, Any], last: Optional[datetime], now: datetime
    ) -> tuple[bool, str, str]:
        if not self._day_allowed(schedule, now):
            return False, "fixed_time", ""
        run_time = self._parse_time(schedule.get("time") or "09:00")
        scheduled = datetime.combine(now.date(), run_time)
        compensation_hours = max(0, int(schedule.get("compensation_hours") or 0))
        end = scheduled + timedelta(hours=compensation_hours)
        if now < scheduled or now > end:
            return False, "fixed_time", ""
        if last and last.date() == now.date():
            return False, "fixed_time", ""
        return True, "fixed_time", ""

    def _monthly_due(
        self, schedule: Dict[str, Any], last: Optional[datetime], now: datetime
    ) -> tuple[bool, str, str]:
        day = max(1, min(28, int(schedule.get("day") or 1)))
        run_time = self._parse_time(schedule.get("time") or "09:00")
        scheduled = datetime(now.year, now.month, day, run_time.hour, run_time.minute)
        compensation_hours = max(0, int(schedule.get("compensation_hours") or 6))
        if now < scheduled or now > scheduled + timedelta(hours=compensation_hours):
            return False, "monthly", ""
        if last and last.year == now.year and last.month == now.month:
            return False, "monthly", ""
        return True, "monthly", ""

    def _condition_due(
        self, condition: Dict[str, Any], last: Optional[datetime], now: datetime
    ) -> tuple[bool, str, str]:
        min_interval = max(1, int(condition.get("min_interval_minutes") or 30))
        if last and now - last < timedelta(minutes=min_interval):
            return False, "condition", ""
        return True, "condition", ""

    async def _trigger_rule(self, rule: Dict[str, Any], source: str, now: datetime):
        rule_id = int(rule["id"])
        target_clients = await self._resolve_clients(rule)
        if str(rule.get("trigger_type")) == "condition":
            target_clients = await self._filter_condition_clients(rule, target_clients, now)

        if not target_clients:
            message = "No online idle browser instances matched the rule"
            await self._write_log(rule_id, None, source, "skipped", message, 0)
            await self._mark_rule(rule_id, now, message)
            return

        params = self._decode_json(rule.get("params_json"))
        try:
            result = await self.plugin_service.create_batch({
                "action": rule["action"],
                "client_ids": target_clients,
                "params": params,
                "operator_id": int(rule.get("update_user") or rule.get("create_user") or 0),
                "title": rule.get("rule_name") or rule["action"],
                "trigger_source": source,
                "trigger_rule_id": rule_id,
            })
            batch_id = int(result.get("batch_id") or 0)
            message = f"Triggered batch #{batch_id} for {len(target_clients)} browser instances"
            await self._write_log(rule_id, batch_id, source, "triggered", message, len(target_clients))
            await self._mark_rule(rule_id, now, message)
        except Exception as exc:
            message = str(exc)[:512]
            logger.exception(f"Trigger rule {rule_id} failed: {message}")
            await self._write_log(rule_id, None, source, "failed", message, len(target_clients))
            await self._mark_rule(rule_id, now, message)

    async def _resolve_clients(self, rule: Dict[str, Any]) -> List[int]:
        target_type = str(rule.get("target_type") or "client")
        target_ids = [int(item) for item in self._decode_json(rule.get("target_ids_json")) if int(item or 0)]
        where = [
            "browser_type IS NOT NULL",
            "browser_type <> ''",
            "status = 1",
            "is_online = 1",
            "admin_id IS NOT NULL",
            "admin_id <> 0",
            "computer_id IS NOT NULL",
            "computer_id <> 0",
        ]
        params: Dict[str, Any] = {}

        if target_type != "all":
            if not target_ids:
                return []
            placeholders = []
            field = {
                "client": "id",
                "computer": "computer_id",
                "employee": "admin_id",
            }.get(target_type, "id")
            for index, value in enumerate(target_ids):
                key = f"target_{index}"
                placeholders.append(f":{key}")
                params[key] = value
            where.append(f"{field} IN ({', '.join(placeholders)})")

        rows = await self.client_dao.fetch_all(
            f"SELECT id FROM fp_spider_client WHERE {' AND '.join(where)} ORDER BY id ASC",
            params,
        )
        client_ids = []
        for row in rows:
            client_id = int(row["id"])
            if self.plugin_service.manager.is_connected(client_id):
                client_ids.append(client_id)
        return client_ids

    async def _filter_condition_clients(
        self, rule: Dict[str, Any], client_ids: List[int], now: datetime
    ) -> List[int]:
        condition = self._decode_json(rule.get("condition_json"))
        condition_type = condition.get("condition_type")
        if condition_type == "cookie_stale":
            hours = max(1, int(condition.get("cookie_stale_hours") or 12))
            threshold = now - timedelta(hours=hours)
            matched = []
            if not client_ids:
                return matched
            placeholders = []
            params: Dict[str, Any] = {"threshold": threshold}
            for index, client_id in enumerate(client_ids):
                key = f"client_{index}"
                placeholders.append(f":{key}")
                params[key] = client_id
            rows = await self.client_dao.fetch_all(
                f"""
                SELECT id FROM fp_spider_client
                WHERE id IN ({', '.join(placeholders)})
                  AND (cookie_uploaded_at IS NULL OR cookie_uploaded_at < :threshold)
                """,
                params,
            )
            matched = [int(row["id"]) for row in rows]
            return matched
        return client_ids

    async def _write_log(
        self,
        rule_id: int,
        batch_id: Optional[int],
        source: str,
        status: str,
        message: str,
        matched_count: int,
    ):
        await self.log_dao.insert({
            "rule_id": rule_id,
            "batch_id": batch_id,
            "trigger_source": source,
            "status": status,
            "message": message[:512],
            "matched_client_count": matched_count,
            "create_time": datetime.now(),
        })

    async def _mark_rule(self, rule_id: int, now: datetime, message: str):
        await self.rule_dao.update({
            "last_trigger_time": now,
            "last_result": message[:256],
            "update_time": now,
        }, {"id": rule_id})

    async def _update_next_time(self, rule: Dict[str, Any], now: datetime):
        # The next time is informational for the admin UI; due checks remain source of truth.
        trigger_type = str(rule.get("trigger_type") or "")
        schedule = self._decode_json(rule.get("schedule_json"))
        next_time = None
        if trigger_type == "interval_window":
            start = self._parse_time(schedule.get("start_time") or "09:00")
            interval = max(1, int(schedule.get("interval_minutes") or 5))
            today_start = datetime.combine(now.date(), start)
            next_time = max(now + timedelta(minutes=interval), today_start)
        elif trigger_type == "fixed_time":
            run_time = self._parse_time(schedule.get("time") or "09:00")
            next_time = datetime.combine(now.date(), run_time)
            if next_time <= now:
                next_time += timedelta(days=1)
        elif trigger_type == "monthly":
            run_time = self._parse_time(schedule.get("time") or "09:00")
            day = max(1, min(28, int(schedule.get("day") or 1)))
            next_time = datetime(now.year, now.month, day, run_time.hour, run_time.minute)
            if next_time <= now:
                month = now.month + 1
                year = now.year
                if month > 12:
                    month = 1
                    year += 1
                next_time = datetime(year, month, day, run_time.hour, run_time.minute)
        if next_time:
            await self.rule_dao.update({"next_trigger_time": next_time}, {"id": int(rule["id"])})

    @staticmethod
    def _decode_json(value: Any) -> Any:
        if value is None or value == "":
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except Exception:
            return {}

    @staticmethod
    def _to_datetime(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @staticmethod
    def _parse_time(value: str) -> time:
        hour, minute = [int(part) for part in str(value).split(":")[:2]]
        return time(hour=hour, minute=minute)

    @staticmethod
    def _time_in_window(current: time, start: time, end: time) -> bool:
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end

    @staticmethod
    def _day_allowed(schedule: Dict[str, Any], now: datetime) -> bool:
        days = schedule.get("days_of_week") or []
        if not days:
            return True
        return now.isoweekday() in {int(day) for day in days}
