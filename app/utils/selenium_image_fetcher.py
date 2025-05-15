# app/utils/selenium_image_fetcher.py

import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

def fetch_tweet_image_urls_via_selenium(short_url: str) -> list[str]:
    """
    t.co 단축 URL을 열어서 tweetPhoto 이미지를 모두 긁어옵니다.
    최소한의 headless 설정만 적용해서, 예전처럼 잘 동작하도록 했습니다.
    """
    opts = Options()
    opts.add_argument("--headless=new")             # Chrome 109+ 권장 headless 모드
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")    # 리눅스 /dev/shm 작을 때 필수
    opts.add_argument("window-size=1920,1080")      # 헤드리스 레이아웃 깨짐 방지
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(options=opts)
    try:
        logger.info("Opening %s", short_url)
        driver.get(short_url)

        # 이미지가 로드될 때까지 대기 (최대 10초)
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div[data-testid='tweetPhoto'] img")
            )
        )

        elems = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='tweetPhoto'] img")
        srcs = [e.get_attribute("src") for e in elems if e.get_attribute("src")]
        logger.info("Found %d images", len(srcs))
        return srcs

    finally:
        driver.quit()