from app.services.file_processing.excel_processor import NormalizedPriceDTO


def dto_to_dict(dto: NormalizedPriceDTO):
    return {
        'import_id': dto.import_id,
        'city': dto.city,
        'product_name': dto.product_name,
        'pharmacy_name': dto.pharmacy_name,
        'is_our': dto.is_our,
        'price': dto.price,
        'purchase_price': dto.purchase_price,
    }
