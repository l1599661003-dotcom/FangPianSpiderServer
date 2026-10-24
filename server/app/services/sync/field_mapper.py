import json
import logging
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List

from server.app.db.base import MySQLBaseDAO

logger = logging.getLogger(__name__)


class FieldMapper:
    """字段映射器，处理特殊字段的转换"""
    
    # 添加MCN缓存字典和状态标志
    _mcn_cache: Dict[str, Dict[str, Any]] = {}
    _mcn_cache_loaded = False

    @staticmethod
    def transform_datetime(value: Any) -> str:
        """转换datetime为字符串"""
        if value:
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M:%S")
            return value
        return None

    @staticmethod
    def transform_json(value: Any) -> str:
        """转换JSON为字符串"""
        if value:
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return value
        return None

    @staticmethod
    def transform_gender(value: Any) -> str:
        """转换gender为字符串"""
        gender_mapping = {
            '男': 1,
            '女': 2
        }

        if value:
            return gender_mapping.get(value, 0)
        return None

    @staticmethod
    def transform_current_tags(value: Any) -> str:
        """转换current_tags为字符串"""
        if isinstance(value, str):
            value = json.loads(value)
        if value:
            tags = []
            tags.extend([tag['taxonomy1Tag'] for tag in value])
            tags.extend([",".join(tag['taxonomy2Tags']) if tag.get('taxonomy2Tags') else '' for tag in value])
            return ','.join(tags)
        return None

    @classmethod
    async def load_mcn_cache(cls) -> None:
        """
        预加载所有MCN信息到缓存
        """
        if cls._mcn_cache_loaded:
            return
            
        try:
            mcn_dao = MySQLBaseDAO('fp_mcn_info')
            # 获取所有现有的MCN记录
            mcn_records = await mcn_dao.fetch_all("SELECT id, mcn_name, mcn_user_id FROM fp_mcn_info WHERE mcn_user_id IS NOT NULL")
            
            # 构建缓存字典
            for record in mcn_records:
                if record.get('mcn_user_id'):
                    cls._mcn_cache[record['mcn_user_id']] = record
                    
            cls._mcn_cache_loaded = True
            logger.info(f"MCN缓存加载完成，共加载 {len(cls._mcn_cache)} 条记录")
        except Exception as e:
            logger.error(f"加载MCN缓存失败: {str(e)}")

    @classmethod
    async def transform_mcn_convert(cls, value: Any) -> Optional[int]:
        """
        转换mcn_id为字符串，使用缓存避免频繁查询数据库
        
        Args:
            value: MCN信息
            
        Returns:
            MCN的ID值
        """
        if not value:
            return None
            
        # 确保缓存已加载
        if not cls._mcn_cache_loaded:
            await cls.load_mcn_cache()
            
        # 尝试从缓存中获取
        mcn_user_id = value if isinstance(value, str) else value.get('userId', '')
        
        if not mcn_user_id:
            return None
            
        # 如果在缓存中已存在，直接返回ID
        if mcn_user_id in cls._mcn_cache:
            return cls._mcn_cache[mcn_user_id]['id']
            
        # 缓存中不存在，需要插入数据库并更新缓存
        try:
            mcn_dao = MySQLBaseDAO('fp_mcn_info')
            mcn_name = value.get('name', '') if isinstance(value, dict) else ''
            
            mcn_info = {
                'mcn_name': mcn_name,
                'mcn_user_id': mcn_user_id
            }
            
            # 插入数据并获取ID
            mcn_id = await mcn_dao.insert(mcn_info)
            mcn_info['id'] = mcn_id
            
            # 更新缓存
            cls._mcn_cache[mcn_user_id] = mcn_info
            
            return mcn_id
        except Exception as e:
            logger.error(f"处理MCN数据失败: {str(e)}")
            return None

    @staticmethod
    def transform_date_to_int(value: Any) -> str:
        """转换date(yyyy-MM-dd)为int"""
        if value:
            return int(value.replace('-', ''))
        return None

    @staticmethod
    def transform_str_to_float(value: Any) -> str:
        """转换str为float，保留2位小数并四舍五入"""
        if value:
            try:
                return round(float(value), 2)
            except (ValueError, TypeError):
                return 0.00
        return None


# 字段转换器映射
FIELD_TRANSFORMERS: Dict[str, Callable] = {
    'datetime': FieldMapper.transform_datetime,
    'json': FieldMapper.transform_json,
    'gender': FieldMapper.transform_gender,
    'content_field': FieldMapper.transform_current_tags,
    'str_to_float': FieldMapper.transform_str_to_float,
    'date_to_int': FieldMapper.transform_date_to_int,
    'mcn_convert': FieldMapper.transform_mcn_convert,
}

# 字段类型映射
FIELD_TYPES: Dict[str, str] = {
    # 'create_time': 'datetime',
    # 'update_time': 'datetime',
    'data': 'json',
    'creator_gender': 'gender',
    'content_field': 'content_field',
    'mcn_id': 'mcn_convert',
    'creator_feature_tags': 'json',
    'creator_personal_tags': 'json',
    'creator_pgy_tag': 'json',
    
    'notes': 'json',
    'page_percent_vo': 'json',
    'long_term_common_note_vo': 'json',
    'long_term_cooperate_note_vo': 'json',
    'trade_names': 'json',
    'note_type_result': 'json',
    'fans_ages': 'json',
    'fans_gender': 'json',
    'fans_interests': 'json',
    'fans_provinces': 'json',
    'fans_cities': 'json',
    'fans_devices': 'json',
    'old_ratio': 'json',
    'region_distribution': 'json',
    'below_ratio': 'json',
    'city_ratio': 'json',
    'city_leve_ratio': 'json',
    'devices_ratio': 'json',
    'interests_ratio': 'json',

    'date_key': 'date_to_int',

    'hundred_like_percent': 'str_to_float',
    'thousand_like_percent': 'str_to_float',
    'imp_median_beyond_rate': 'str_to_float',
    'read_median_beyond_rate': 'str_to_float',
    'interaction_rate': 'str_to_float',
    'interaction_beyond_rate': 'str_to_float',
    'video_full_view_rate': 'str_to_float',
    'video_full_view_beyond_rate': 'str_to_float',
    'picture3s_view_rate': 'str_to_float',

    'video_surpass_rate': 'str_to_float',
    'estimate_picture_cpm': 'str_to_float',
    'estimate_picture_cpm_compare': 'str_to_float',
    'estimate_video_cpm': 'str_to_float',
    'estimate_video_cpm_compare': 'str_to_float',
    'estimate_picture_engage_cost': 'str_to_float',
    'estimate_picture_engage_cost_compare': 'str_to_float',
    'estimate_video_engage_cost': 'str_to_float',
    'estimate_video_engage_cost_compare': 'str_to_float',
    'picture_surpass_rate': 'str_to_float',
    'picture_read_cost': 'str_to_float',
    'video_case': 'str_to_float',
    'video_read_cost': 'str_to_float',
}
