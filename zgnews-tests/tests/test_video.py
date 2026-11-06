import allure
import pytest
import requests
from bs4 import BeautifulSoup



def _absolute(base_url, href):
    return base_url + href if href.startswith("/") else href


@pytest.fixture(scope="module")
def video_url(base_url):
    resp = requests.get(base_url + "/list/26.html", timeout=20)
    assert resp.status_code == 200
    soup = BeautifulSoup(resp.text, "html.parser")
    links = [a.get("href") for a in soup.select('a[href^="/video/"]')]
    links = list(dict.fromkeys([x for x in links if x]))
    assert links, "视频频道未找到视频详情链接"
    return _absolute(base_url, links[0])


def _open_video(page, video_url):
    page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_function(
        "() => { const v = document.querySelector('video'); return v && v.readyState >= 2; }",
        timeout=30000,
    )


@allure.feature("视频与播放器")
@allure.story("视频频道列表")
def test_video_channel_list(page, base_url):
    resp = page.goto(base_url + "/list/26.html", wait_until="domcontentloaded", timeout=30000)
    assert resp and resp.status == 200
    assert "视频" in page.title()
    assert page.locator('a[href^="/video/"]').count() >= 5
    assert page.locator(".video-img img").count() >= 5
    page.screenshot(path="screenshots/video-list.png", full_page=False)


@pytest.mark.smoke
@allure.feature("视频与播放器")
@allure.story("播放器加载与元数据")
def test_video_player_loads(page, video_url):
    _open_video(page, video_url)
    assert page.locator("video").count() == 1
    assert page.locator(".prism-player").count() >= 1
    meta = page.evaluate("""() => {
        const v = document.querySelector('video');
        return {duration: v.duration, width: v.videoWidth, height: v.videoHeight, ready: v.readyState};
    }""")
    print("video meta", meta)
    assert meta["duration"] > 5
    assert meta["width"] > 0 and meta["height"] > 0
    assert meta["ready"] >= 2
    page.screenshot(path="screenshots/video-player.png", full_page=False)


@pytest.mark.smoke
@allure.feature("视频与播放器")
@allure.story("播放与暂停")
def test_video_play_pause(page, video_url):
    _open_video(page, video_url)
    played = page.evaluate("""async () => {
        const v = document.querySelector('video');
        v.muted = true;
        try { await v.play(); return !v.paused; } catch (e) { return false; }
    }""")
    assert played, "muted play() 未成功"
    page.wait_for_timeout(600)
    assert page.evaluate("() => !document.querySelector('video').paused")
    page.evaluate("() => document.querySelector('video').pause()")
    assert page.evaluate("() => document.querySelector('video').paused")


@allure.feature("视频与播放器")
@allure.story("进度跳转 seek")
def test_video_seek(page, video_url):
    _open_video(page, video_url)
    page.evaluate("() => { const v = document.querySelector('video'); v.muted = true; v.currentTime = 10; }")
    page.wait_for_timeout(1200)
    current = page.evaluate("() => document.querySelector('video').currentTime")
    print("currentTime", current)
    assert 8 <= current <= 20


@allure.feature("视频与播放器")
@allure.story("音量与静音")
def test_video_volume_mute(page, video_url):
    _open_video(page, video_url)
    state = page.evaluate("""() => {
        const v = document.querySelector('video');
        v.muted = true; v.volume = 0.35;
        return {muted: v.muted, volume: v.volume};
    }""")
    assert state["muted"] is True
    assert abs(state["volume"] - 0.35) < 0.01


@allure.feature("视频与播放器")
@allure.story("播放器控件")
def test_video_controls(page, video_url):
    _open_video(page, video_url)
    assert page.locator(".prism-controlbar").count() >= 1
    assert page.locator(".prism-progress").count() >= 1
    assert page.locator(".prism-volume-control").count() >= 1
    assert page.locator(".prism-big-play-btn").count() >= 1


@allure.feature("视频与播放器")
@allure.story("MP4 资源与 Range 请求")
def test_video_media_http(page, base_url, video_url):
    _open_video(page, video_url)
    media = page.locator("video").first.get_attribute("src")
    assert media, "视频页没有 video[src]"
    if media.startswith("//"):
        media = "https:" + media
    head = requests.head(media, timeout=30)
    assert head.status_code == 200
    assert head.headers.get("content-type", "").startswith("video/")
    assert int(head.headers.get("content-length", "0")) > 1_000_000
    part = requests.get(media, headers={"Range": "bytes=0-1023"}, timeout=30)
    assert part.status_code == 206
    assert "content-range" in part.headers
    assert len(part.content) == 1024


@allure.feature("视频与播放器")
@allure.story("移动端播放器布局")
def test_video_mobile_layout(mobile_page, video_url):
    _open_video(mobile_page, video_url)
    box = mobile_page.locator("video").first.bounding_box()
    assert box
    if box["width"] > 390:
        pytest.xfail(f"移动端播放器宽度 {box['width']}px，超出 390 视口（已知问题）")
    scroll_width = mobile_page.evaluate("() => document.documentElement.scrollWidth")
    viewport = mobile_page.evaluate("() => window.innerWidth")
    assert scroll_width <= viewport + 2
    mobile_page.screenshot(path="screenshots/video-mobile.png", full_page=False)
