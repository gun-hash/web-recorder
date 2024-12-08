import asyncio
import os
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

# Ensure the videos directory exists
Path("videos").mkdir(exist_ok=True)

async def record_website(url, video_id):
    """Record a website and save the video."""
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                record_video_dir=f"videos/{video_id}",
                record_video_size={'width': 1280, 'height': 720}
            )
            
            page = await context.new_page()
            
            # Increase timeout to 60 seconds and add wait until options
            print(f"Navigating to {url}...")
            await page.goto(url, 
                            timeout=60000,  # 60 seconds
                            wait_until="domcontentloaded")  # Wait until domcontentloaded
            
            # Wait for any animations or dynamic content to load
            await page.wait_for_timeout(1000)  # Wait additional 1 second
            
            # Scroll the page in increments
            scroll_increment = 100
            scroll_pause = 100  # milliseconds
            page_height = await page.evaluate("document.body.scrollHeight")
            
            for position in range(0, page_height, scroll_increment):
                await page.evaluate(f"window.scrollTo(0, {position})")
                await page.wait_for_timeout(scroll_pause)
            
            print("Recording complete, closing context...")
            await context.close()
            await browser.close()
            
            # Get the recorded video file
            video_path = list(Path(f"videos/{video_id}").glob("*.webm"))[0]
            return str(video_path)
            
    except Exception as e:
        print(f"Error recording website: {str(e)}")
        raise Exception(f"Failed to record website: {str(e)}")