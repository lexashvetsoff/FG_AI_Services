import enum


class SourceType(str, enum.Enum):
    excel = 'excel'
    onec = '1c'
    api = 'api'


class ImportStatus(str, enum.Enum):
    uploaded = 'uploaded'
    processing = 'processing'
    done = 'done'
    error = 'error'


class ReportGenerationStatus(enum.Enum):
    pending = 'pending'      # ещё не начата
    processing = 'processing' # в процессе
    ready = 'ready'           # отчёты готовы
    failed = 'failed'         # ошибка
