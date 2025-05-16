import asyncio
from typing import List
from .selenium_image_fetcher import fetch_tweet_image_urls_via_selenium

class TcoResolver:
    """
    Blocking Selenium 호출을 asyncio.to_thread 로 감싸서 비동기로 사용
    """
    async def resolve(self, orig_urls: List[str]) -> List[str]:
        resolved: List[str] = []
        for url in orig_urls:
            if "t.co/" in url or "twitter.com/photo" in url:
                imgs = await asyncio.to_thread(fetch_tweet_image_urls_via_selenium, url)
                resolved.append(imgs[0] if imgs else url)
            else:
                resolved.append(url)
        return resolved