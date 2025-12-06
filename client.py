import httpx, pathlib, json, math, io, datetime, sys
from typing import Literal
from bs4 import BeautifulSoup as bs
from urllib.parse import urljoin, urlsplit
from PIL import Image
from structs import *

class ComiciClient:
    main_client: httpx.Client
    cdn_client: httpx.Client
    user_id: int | None

    HOST = "https://comic-growl.com"
    CONFIG_PATH_DEFAULT = "config.json"

    USER_AGENT_DEFAULT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"
    PROXY_DEFAULT: str | None = None
    COOKIES_DEFAULT: str | None = None

    def load_dict_config(self, config: dict):
        if "cookies" in config:
            self.COOKIES_DEFAULT = config["cookies"]
        if "proxy" in config:
            self.PROXY_DEFAULT = config["proxy"]
        if "user_agent" in config:
            self.USER_AGENT_DEFAULT = config["user_agent"]
        if "host" in config:
            self.HOST = "https://" + urlsplit(config["host"]).hostname

    def load_config_file(self, config_path: str | pathlib.Path = None):
        if not config_path: 
            config_path = self.CONFIG_PATH_DEFAULT
        else:
            config_path = pathlib.Path(config_path)
            if not config_path.exists() or not config_path.is_file(): 
                return
        
        with open(config_path, "r", encoding="utf-8") as f:
            self.load_dict_config(json.load(f))

    def __init__(
            self, 
            cookies: dict[str, str] | str | pathlib.Path | None = None, 
            user_id: int | str | None = None, 
            proxy: str | None = None, 
            user_agent: str | None = None,
            host: str | None = None,
            custom_config_path: str | pathlib.Path | None = None,
        ):

        self.load_config_file(custom_config_path if custom_config_path else "")

        self.user_id = user_id
        self.main_client = httpx.Client(
            headers={"User-Agent": user_agent if user_agent else self.USER_AGENT_DEFAULT},
            proxy=proxy if proxy else self.PROXY_DEFAULT, 
            transport=httpx.HTTPTransport(retries=3)
        )

        if host:
            self.HOST = "https://" + urlsplit(host).hostname

        self.cdn_client = httpx.Client(
            headers={
                "User-Agent": user_agent if user_agent else self.USER_AGENT_DEFAULT,
                "sec-fetch-dest": "image",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "dnt": "1",
                "sec-gpc": "1",
                "priority": "u=5, i",
                "te": "trailers",
            },
            transport=httpx.HTTPTransport(retries=3)
        )

        if cookies is None: return
        if isinstance(cookies, dict):
            self.main_client.cookies.update(cookies)
        elif isinstance(cookies, pathlib.Path) or isinstance(cookies, str):
            self.update_cookies_from_CookieEditorJson(cookies)

    def update_cookies_from_CookieEditorJson(self, path: str | pathlib.Path = None, ignore_expired: bool = False):
        if isinstance(path, str): path = pathlib.Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                json_dict = json.load(f)
                if isinstance(json_dict, list) and len(json_dict) > 0:
                    if not ignore_expired:
                        earliest_expiration_timestamp = min([
                            item.get('expirationDate', sys.maxsize) 
                            for item in json_dict
                            if item['name'] not in ('__stripe_sid', )
                        ])
                        if earliest_expiration_timestamp < datetime.datetime.now().timestamp(): 
                            raise ValueError(f"Cookies {[item['name'] for item in json_dict if item.get('expirationDate', sys.maxsize) < datetime.datetime.now().timestamp()]} expired {earliest_expiration_timestamp} < {datetime.datetime.now().timestamp()}, please update your cookies")
                    
                    domain = json_dict[0]['domain']
                    if domain.lstrip('.') not in self.HOST:
                        raise ValueError(f"Cookies domain mismatch, {domain} != {urlsplit(self.HOST).hostname}")

                    self.main_client.cookies.update({item['name']: item['value'] for item in json_dict})
                else:
                    raise ValueError("Invalid Cookie-Editor JSON format")
        else:
            raise FileNotFoundError("Cookies file not found")

    def search(
        self, 
        keyword: str, 
        page: int = 0, 
        size: int = 30, 
        _filter: Literal["series", "seriesofauthors", "articles"] = "series"
    ) -> tuple[list[MangaStoreItem], bool]:
        response = self.main_client.get(
            urljoin(self.HOST, "/search"),
            params={
                "keyword": keyword,
                "page": page,
                "size": size,
                "filter": _filter
            }
        )
        response.raise_for_status()

        resultList = list()

        soup = bs(response.text, "html.parser")

        user_id = soup.find("span", {"id": "login_user_id"}).text
        if user_id: self.user_id = user_id

        series_list = soup.find("div", {"class": "series-list"})
        if not series_list: return resultList, False
        for manga_item in series_list.find_all("div", {"class": "manga-store-item"}):
            link = manga_item.find("a")
            resultList.append(MangaStoreItem(
                href=link["href"] if link.has_attr("href") else link['data-href'],
                title=manga_item.find("h2", {"class": "manga-title"}).text.strip('\n\t '),
                author=link.find("span", {"class": "manga-author"}).text.strip('\n ').split('\n') if _filter != "articles" else "",
            ))
        
        has_next_page = False
        pages_list = soup.find("ul", {"class": "mode-paging"})
        if not pages_list: 
            return resultList, False

        for img in pages_list.find_all("img"):
            if img.has_attr("data-src") or img.has_attr("src"):
                if "paging_next" in img["data-src"] if img.has_attr("data-src") else img["src"]:
                    has_next_page = True
                    break
        
        return resultList, has_next_page
    
    def series_pagingList(self, href: str | None = None, series_id: str | None = None, sort: int = 2, page: int = 0, limit: int = 50) -> tuple[list[MangaEpisodeItem], bool]:
        if not href and not series_id: 
            raise ValueError("Either href or series_id must be provided")
        
        if href:
            urlpath_splited = urlsplit(href).path.rstrip("/").split("/")
            if len(urlpath_splited) < 2: 
                raise ValueError("Invalid href")
            elif not urlpath_splited[-2] == "series":
                raise ValueError("Invalid href")
            series_id = urlpath_splited[-1]

        response = self.main_client.get(
            urljoin(self.HOST, f"/series/{series_id}/pagingList"),
            params={
                "s": sort,
                "page": page,
                "limit": limit
            }
        )
        response.raise_for_status()

        resultList = list()

        soup = bs(response.text, "html.parser")
        
        user_id = soup.find("span", {"id": "login_user_id"}).text
        if user_id: self.user_id = user_id

        series_ep_list = soup.find("div", {"class": "series-ep-list"})

        if not series_ep_list: return resultList, False

        for ep_item in series_ep_list.find_all("div", {"class": "series-ep-list-item"}):
            link = ep_item.find("a")

            main_info = ep_item.find("div", {"class": "series-ep-list-item-main"})
            title = main_info.find("span", {"class": "series-ep-list-item-h-text"}).text
            update_date = main_info.find("p", {"class": "series-ep-list-date"}).text.strip('\n')

            symbols = list()

            symbols_to_check = ep_item.find("div", {"class": "series-ep-list-symbols"})
            symbols_to_check_list = symbols_to_check.find("div", {"class": "mode-list"})
            for child in symbols_to_check_list.children:
                if child.name in ("span", "div"):
                    symbols.append(child.text.strip('\t\n'))
                elif child.name == "img":
                    if child.has_attr("alt"):
                        alt: str = child["alt"].strip("「」")
                        if alt.endswith("無料"):
                            symbols.append(alt)
            
            resultList.append(MangaEpisodeItem(
                href=link["data-href"] if link.has_attr("data-href") else "",
                title=title,
                update_date=update_date,
                symbols=symbols
            ))

        return resultList, True if soup.find("a", {"class": "next-page"}) else False

    def episodes(self, href: str | None = None, episode_id: str | None = None) -> str:
        if not href and not episode_id: 
            raise ValueError("Either href or episode_id must be provided")
    
        if href: 
            urlpath_splited = urlsplit(href).path.rstrip("/").split("/")
            if len(urlpath_splited) < 2: 
                raise ValueError("Invalid href")
            elif not urlpath_splited[-2] == "episodes":
                raise ValueError("Invalid href")
            episode_id = urlpath_splited[-1]

        response = self.main_client.get(
            urljoin(self.HOST, f"/episodes/{episode_id}/"),
        )
        response.raise_for_status()

        soup = bs(response.text, "html.parser") 
        content_box_detail = soup.find("div", {"class": "content-box-detail"})

        user_id = soup.find("span", {"id": "login_user_id"}).text
        if user_id: self.user_id = user_id

        comici_viewer = content_box_detail.find("div", {"id": "comici-viewer"})
        if not comici_viewer: return ""
        return comici_viewer["comici-viewer-id"]
    
    def book_info(self, comici_viewer_id: str) -> Info:
        response = self.main_client.get(
            urljoin(self.HOST, f"/book/Info"),
            params={
                "comici-viewer-id": comici_viewer_id
            }
        )
        response.raise_for_status()

        resJson = response.json()
        if not resJson["code"] == 1000:
            raise Exception(resJson['message'])
        
        resJson['result']['_id'] = resJson['result'].pop('id')
        return Info(**resJson['result'])
    
    def book_episodeInfo(self, comici_viewer_id: str, isPreview: bool = False) -> list[EpisodeInfo]:
        response = self.main_client.get(
            urljoin(self.HOST, f"/book/episodeInfo"),
            params={
                "comici-viewer-id": comici_viewer_id,
                "isPreview": isPreview
            }
        )
        response.raise_for_status()

        resJson = response.json()
        if not resJson["code"] == 1000:
            raise Exception(resJson['message'])
        
        resultList = list()
        for r in resJson["result"]:
            r["_id"] = r.pop("id")
            resultList.append(EpisodeInfo(**r))

        return resultList
    
    def book_contentsInfo(self, comici_viewer_id: str, page_from: int, page_to: int, user_id: int | str = "0") -> list[ContentsInfo]:
        response = self.main_client.get(
            urljoin(self.HOST, f"/book/contentsInfo"),
            params={
                "user-id": user_id if str(user_id) != "0" else (self.user_id if self.user_id else "0"),
                "comici-viewer-id": comici_viewer_id,
                "page-from": page_from,
                "page-to": page_to
            }
        )
        response.raise_for_status()

        resJson = response.json()
        if not resJson["code"] == 1000:
            raise Exception(resJson['message'])
        
        return [ContentsInfo(**r) for r in resJson["result"]]
    
    @staticmethod
    def descramble_image(image: bytes | io.BytesIO, scramble: list[int]) -> Image.Image:

        BLOCKS_PER_SIDE = math.floor(math.sqrt(len(scramble)))

        if isinstance(image, bytes):
            image = io.BytesIO(image)

        img: Image.Image = Image.open(image)

        width = img.width - img.width % BLOCKS_PER_SIDE
        height = img.height - img.height % BLOCKS_PER_SIDE
        tile_w = width // BLOCKS_PER_SIDE
        tile_h = height // BLOCKS_PER_SIDE

        result: Image.Image = Image.new("RGB", (width, height))

        def get_tile_info(row: int, col: int) -> tuple[int, int, int, int]:
            return (
                col * tile_w,
                row * tile_h,
                (col + 1) * tile_w,
                (row + 1) * tile_h
            )

        pos = list()
        for col in range(BLOCKS_PER_SIDE):
            for row in range(BLOCKS_PER_SIDE):
                pos.append((row, col))

        scrambled_pos = [pos[i] for i in scramble]
        for i, (row, col) in enumerate(scrambled_pos):
            tile_info = get_tile_info(row, col)
            tile = img.crop(tile_info)
            result.paste(tile, get_tile_info(pos[i][0], pos[i][1]))

        img.close()
        return result
    
    def get_and_descramble_image(self, contentsInfo: ContentsInfo, episode_id: str) -> Image.Image:
        self.cdn_client.headers.update({
            "Referer": urljoin(self.HOST, f"/episodes/{episode_id}/"),
            "Origin": self.HOST,
        })
        response = self.cdn_client.get(
            contentsInfo.imageUrl
        )
        response.raise_for_status()

        return ComiciClient.descramble_image(
            response.content, 
            contentsInfo.scramble
        )