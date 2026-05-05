import re


def enforce_import_filter(sql: str, import_id: str) -> str:
    sql_clean = sql.strip()

    # если уже есть WHERE
    if 'where' in sql.lower():
        return re.sub(
            r"where",
            f"WHERE import_id = '{import_id}' AND",
            sql_clean,
            count=1,
            flags=re.IGNORECASE
        )
    
    # если WHERE нет
    if 'limit' in sql.lower():
        return re.sub(
            r"limit",
            f"WHERE import_id = '{import_id}' LIMIT",
            sql_clean,
            flags=re.IGNORECASE
        )
    
    return f"{sql_clean} WHERE import_id = '{import_id}'"
