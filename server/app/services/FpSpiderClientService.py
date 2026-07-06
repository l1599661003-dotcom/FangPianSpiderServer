from server.app.db.base import MySQLBaseDAO


class FpSpiderClientService(MySQLBaseDAO):

    def __init__(self):
        super().__init__("fp_spider_client")


spider_client_service = FpSpiderClientService()