import re


def validate_sql(sql: str, import_id: str) -> bool:
    sql = sql.lower()

    # запрещенные операции
    forbidden = ['delete', 'update', 'inserrt', 'drop', 'alter']

    if any(word in sql for word in forbidden):
        return False
    
    # только select
    if not sql.strip().startswith('select'):
        return False
    
    # limit обязателен
    if 'limit' not in sql:
        return False
    
    if f"import_id = '{import_id.lower()}'" not in sql:
        return False
    
    return True
