"""Search router: search attractions (Mock or real Bing/Google API)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.task import SearchRequest, SearchResponse, SearchResult
from app.config import settings

router = APIRouter()

# Mock search results for Hangzhou attractions
MOCK_RESULTS = [
    SearchResult(title="西湖风景区", url="https://zh.wikipedia.org/wiki/西湖", snippet="西湖位于杭州市中心，是中国著名的风景名胜区，以\"西湖十景\"闻名于世。"),
    SearchResult(title="灵隐寺", url="https://zh.wikipedia.org/wiki/灵隐寺", snippet="灵隐寺是中国佛教禅宗十大古刹之一，始建于东晋咸和元年(326年)。"),
    SearchResult(title="千岛湖", url="https://zh.wikipedia.org/wiki/千岛湖", snippet="千岛湖位于杭州市淳安县境内，是世界上岛屿数量最多的人工湖。"),
    SearchResult(title="宋城", url="https://zh.wikipedia.org/wiki/宋城", snippet="宋城景区再现了宋代都市的繁华景象，《宋城千古情》是其标志性演出。"),
    SearchResult(title="西溪湿地", url="https://zh.wikipedia.org/wiki/西溪湿地", snippet="西溪国家湿地公园是罕见的城中次生湿地，被评为国家5A级旅游景区。"),
    SearchResult(title="雷峰塔", url="https://zh.wikipedia.org/wiki/雷峰塔", snippet="雷峰塔位于西湖南岸，因《白蛇传》传说而闻名，登塔可俯瞰西湖全景。"),
    SearchResult(title="河坊街", url="https://zh.wikipedia.org/wiki/河坊街", snippet="河坊街是杭州著名的历史街区，汇聚传统小吃、手工艺品和特色商铺。"),
    SearchResult(title="六和塔", url="https://zh.wikipedia.org/wiki/六和塔", snippet="六和塔位于钱塘江畔，始建于北宋开宝三年(970年)，可登塔观钱塘江潮。"),
    SearchResult(title="断桥残雪", url="https://zh.wikipedia.org/wiki/断桥残雪", snippet="断桥是西湖最著名的景点之一，《白蛇传》中许仙与白娘子在此相遇。"),
    SearchResult(title="龙井村", url="https://zh.wikipedia.org/wiki/龙井村", snippet="龙井村以盛产顶级西湖龙井茶闻名，可体验采茶、制茶和品茶文化。"),
]


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest, user: User = Depends(get_current_user)):
    """Search for attractions. Uses mock data or real search API."""
    if settings.BING_SEARCH_API_KEY or settings.GOOGLE_SEARCH_API_KEY:
        # TODO: implement real search API call
        pass

    # Mock: filter results by query keywords
    query_lower = req.query.lower()
    filtered = [
        r for r in MOCK_RESULTS
        if any(kw in r.title.lower() or kw in r.snippet.lower()
               for kw in query_lower.split() if len(kw) > 1)
    ] if query_lower else MOCK_RESULTS

    if not filtered:
        filtered = MOCK_RESULTS  # Return all if no match

    # Paginate
    page_size = 10
    start = (req.page - 1) * page_size
    paginated = filtered[start:start + page_size]

    return SearchResponse(results=paginated, total=len(filtered))
