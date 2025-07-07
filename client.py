import httpx
from .config import settings
from .exceptions import ApiError

class ApiClient:
    def __init__(self):
        headers = {}
        if settings.django_key:
            headers['Authorization'] = f"Token {settings.django_key}"
        self.client = httpx.AsyncClient(
            base_url=settings.django_url.rstrip('/') + '/api',
            headers=headers,
            timeout=10
        )

    async def post_pedidos(self, pedidos: list[dict]) -> dict:
        """
        Envía la lista de pedidos a Django en /pedidos/bulk/
        """
        resp = await self.client.post("/pedidos/bulk/", json=pedidos)
        if resp.status_code >= 400:
            raise ApiError(f"Status {resp.status_code}: {resp.text}")
        return resp.json()
