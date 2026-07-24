"""Search router: DuckDuckGo + Bing, with local mock fallback."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.task import SearchRequest, SearchResponse, SearchResult
from app.services import search_service

router = APIRouter()

# Mock search results for Hangzhou attractions (used when web search fails)
MOCK_RESULTS = [
    SearchResult(title="西湖风景区", url="https://zh.wikipedia.org/wiki/西湖", snippet="西湖位于杭州市中心，是中国著名的风景名胜区，以\"西湖十景\"闻名于世。", source="mock"),
    SearchResult(title="灵隐寺", url="https://zh.wikipedia.org/wiki/灵隐寺", snippet="灵隐寺是中国佛教禅宗十大古刹之一，始建于东晋咸和元年(326年)。", source="mock"),
    SearchResult(title="千岛湖", url="https://zh.wikipedia.org/wiki/千岛湖", snippet="千岛湖位于杭州市淳安县境内，是世界上岛屿数量最多的人工湖。", source="mock"),
    SearchResult(title="宋城", url="https://zh.wikipedia.org/wiki/宋城", snippet="宋城景区再现了宋代都市的繁华景象，《宋城千古情》是其标志性演出。", source="mock"),
    SearchResult(title="西溪湿地", url="https://zh.wikipedia.org/wiki/西溪湿地", snippet="西溪国家湿地公园是罕见的城中次生湿地，被评为国家5A级旅游景区。", source="mock"),
    SearchResult(title="雷峰塔", url="https://zh.wikipedia.org/wiki/雷峰塔", snippet="雷峰塔位于西湖南岸，因《白蛇传》传说而闻名，登塔可俯瞰西湖全景。", source="mock"),
    SearchResult(title="河坊街", url="https://zh.wikipedia.org/wiki/河坊街", snippet="河坊街是杭州著名的历史街区，汇聚传统小吃、手工艺品和特色商铺。", source="mock"),
    SearchResult(title="六和塔", url="https://zh.wikipedia.org/wiki/六和塔", snippet="六和塔位于钱塘江畔，始建于北宋开宝三年(970年)，可登塔观钱塘江潮。", source="mock"),
    SearchResult(title="断桥残雪", url="https://zh.wikipedia.org/wiki/断桥残雪", snippet="断桥是西湖最著名的景点之一，《白蛇传》中许仙与白娘子在此相遇。", source="mock"),
    SearchResult(title="龙井村", url="https://zh.wikipedia.org/wiki/龙井村", snippet="龙井村以盛产顶级西湖龙井茶闻名，可体验采茶、制茶和品茶文化。", source="mock"),
]


@router.post("", response_model=SearchResponse)
async def search(req: SearchRequest, user: User = Depends(get_current_user)):
    """Search for attractions. Uses DuckDuckGo + Bing, falling back to mock data."""
    query_lower = req.query.lower().strip() if req.query else ""

    # Try real web search first
    web_results = []
    try:
        raw = await search_service.web_search(req.query, num=10)
        web_results = [
            SearchResult(title=r["title"], url=r["url"], snippet=r["snippet"], source="search_engine")
            for r in raw
            if r.get("title") and r.get("url")
        ]
    except Exception:
        web_results = []

    if web_results:
        # Simple keyword filter if query is present
        if query_lower:
            keywords = [kw for kw in query_lower.split() if len(kw) > 1]
            filtered = [
                r for r in web_results
                if any(kw in r.title.lower() or kw in r.snippet.lower() for kw in keywords)
            ]
            if filtered:
                web_results = filtered
        # Paginate
        page_size = 10
        start = (req.page - 1) * page_size
        paginated = web_results[start:start + page_size]
        return SearchResponse(results=paginated, total=len(web_results))

    # Fallback: mock local data
    if query_lower:
        keywords = [kw for kw in query_lower.split() if len(kw) > 1]
        filtered = [
            r for r in MOCK_RESULTS
            if any(kw in r.title.lower() or kw in r.snippet.lower() for kw in keywords)
        ] if keywords else MOCK_RESULTS
        if not filtered:
            filtered = MOCK_RESULTS
    else:
        filtered = MOCK_RESULTS

    page_size = 10
    start = (req.page - 1) * page_size
    paginated = filtered[start:start + page_size]
    return SearchResponse(results=paginated, total=len(filtered))
