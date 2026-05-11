import logging


class ChatRouter:
    ANALYTICAL_KEYWORDS = [
        "анализ", "почему", "конкурент", "дороже", "дешевле",
        "где мы", "кто", "рекомендац", "сравни", "какой"
    ]

    SQL_KEYWORDS = [
        "покажи", "выведи", "список", "таблица", "топ", "select"
    ]

    # def detect_mode(self, question: str) -> str:
    #     q = question.lower()

    #     if any(k in q for k in self.ANALYTICAL_KEYWORDS):
    #         logging.info('ChatRouter: Detect rout context')
    #         return 'context'
        
    #     if any(k in q for k in self.SQL_KEYWORDS):
    #         logging.info('ChatRouter: Detect rout sql')
    #         return 'sql'
        
    #     # fallback
    #     logging.info('ChatRouter: Fallback rout context')
    #     return 'context'
    def detect_mode(self, question: str) -> str:
        q = question.lower()

        if any(k in q for k in self.ANALYTICAL_KEYWORDS):
            logging.info('ChatRouter: Detect rout sql')
            return 'sql'
        
        if any(k in q for k in self.SQL_KEYWORDS):
            logging.info('ChatRouter: Detect rout sql')
            return 'sql'
        
        # fallback
        logging.info('ChatRouter: Fallback rout context')
        return 'context'
