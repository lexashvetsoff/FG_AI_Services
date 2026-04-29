import httpx
from app.config import settings


timeout_config = httpx.Timeout(
    connect=5.0,
    read=1200.0,   # 20 минут (test)
    write=10.0,
    pool=5.0
)


class AnalystClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    async def generate(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                f'{self.base_url}/api/generate',
                json={
                    'model': settings.ANALYST_LLM_MODEL,
                    'prompt': prompt,
                    'stream': False
                }
            )
            response.raise_for_status()

        data = response.json()
        return data.get('response', '')
