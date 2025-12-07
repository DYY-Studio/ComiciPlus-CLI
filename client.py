import httpx, pathlib, json, math, io, datetime, sys, time
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

    NEW_VERSION = False

    def set_host(self, host: str):
        host = "https://" + (urlsplit(host).hostname if urlsplit(host).hostname else host)
        if not self.is_supported_version(host):
            raise ValueError(f"Unsupported host: {host}")

    def load_dict_config(self, config: dict):
        if "cookies" in config:
            self.COOKIES_DEFAULT = config["cookies"]
        if "proxy" in config:
            self.PROXY_DEFAULT = config["proxy"]
        if "user_agent" in config:
            self.USER_AGENT_DEFAULT = config["user_agent"]
        if "host" in config:
            host = config["host"]
            self.HOST = "https://" + (urlsplit(host).hostname if urlsplit(host).hostname else host)

    def load_config_file(self, config_path: str | pathlib.Path = None):
        if not config_path: 
            config_path = pathlib.Path(self.CONFIG_PATH_DEFAULT)
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
            timeout=20.0,
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
            transport=httpx.HTTPTransport(retries=3),
            proxy=proxy if proxy else self.PROXY_DEFAULT,
        )

        if not self.is_supported_version():
            self.NEW_VERSION = True

        if cookies is None: 
            if self.COOKIES_DEFAULT is not None:
                self.update_cookies_from_CookieEditorJson(self.COOKIES_DEFAULT)
            return
        if isinstance(cookies, dict):
            self.main_client.cookies.update(cookies)
        elif isinstance(cookies, pathlib.Path) or isinstance(cookies, str):
            self.update_cookies_from_CookieEditorJson(cookies)

    def update_cookies_from_CookieEditorJson(
            self, 
            path: str | pathlib.Path = None, 
            ignore_expired: bool = False,
            ignore_domain_mismatch: bool = True
        ):
        if isinstance(path, str): path = pathlib.Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                json_dict = json.load(f)
                if isinstance(json_dict, list) and len(json_dict) > 0:
                    if not ignore_expired:
                        earliest_expiration_timestamp = min([
                            item.get('expirationDate', sys.maxsize) 
                            for item in json_dict
                            if item['name'].startswith('_g')
                        ])
                        if earliest_expiration_timestamp < datetime.datetime.now().timestamp(): 
                            raise ValueError(f"Cookies {[item['name'] for item in json_dict if item.get('expirationDate', sys.maxsize) < datetime.datetime.now().timestamp()]} expired {earliest_expiration_timestamp} < {datetime.datetime.now().timestamp()}, please update your cookies")
                    
                    # all website that use ComiciPlus share login infomation.
                    # maybe we donot need to check domain
                    if not ignore_domain_mismatch:
                        domain = json_dict[0]['domain']
                        if domain.lstrip('.') not in self.HOST:
                            raise ValueError(f"Cookies domain mismatch, {domain} != {urlsplit(self.HOST).hostname}")

                    self.main_client.cookies.update({item['name']: item['value'] for item in json_dict})

                    if self.NEW_VERSION:
                        self.user_id, user_name = self.api_popups()
                        if not self.user_id or not user_name:
                            raise ValueError("Cookies invalid, please update your cookies")
                else:
                    raise ValueError("Invalid Cookie-Editor JSON format")
        else:
            raise FileNotFoundError("Cookies file not found")

    def get_all_support_sites(self) -> list[str]:
        response = self.main_client.get(
            "https://comici.co.jp/business/comici-plus",
        )
        response.raise_for_status()

        resultList = list()

        soup = bs(response.text, "html.parser")
        for cards in soup.find_all("div", {"data-structure":"m-cards"}):
            for card in cards.find_all("div", {"data-structure": "m-card"}):
                link = card.find("a")
                if link.has_attr("href") and not link["href"].startswith("javascript"):
                    resultList.append(link["href"])
        
        return resultList
    
    def is_supported_version(self, host: str | None = None, soup: bs | None = None):
        if not soup:
            response = self.main_client.get(
                host if host else self.HOST,
            )
            response.raise_for_status()

            time.sleep(0.2)

            soup = bs(response.text, "html.parser")

        contentLink = soup.find("span", {"id": "contentLink"}) 
        return True if contentLink else False
    
    def get_user_id_and_name(self, soup: bs | None = None) -> tuple[str | None, str | None]:
        if not soup:
            response = self.main_client.get(
                self.HOST,
            )
            response.raise_for_status()

            time.sleep(0.2)

            soup = bs(response.text, "html.parser")
        
        login_user_name = soup.find("span", {"id": "login_user_name"})
        login_user_id = soup.find("span", {"id": "login_user_id"})
        
        return login_user_id.text.strip("\n\t ") if login_user_id else None, \
                login_user_name.text.strip("\n\t ") if login_user_name else None
    
    
    
    def bookshelf(self, page: int = 0, bookshelf_type: Literal["", "favorite", "buying", "liking"] = "") -> tuple[list[BookshelfItem], bool]:

        user_id, user_name = self.get_user_id_and_name()
        if not user_name:
            raise ValueError("Not login")

        response = self.main_client.get(
            urljoin(self.HOST, f"/{user_name}/bookshelf/{bookshelf_type}"),
            params={
                "page": page if page > 0 else 0
            }
        )
        response.raise_for_status()

        resultList: list[BookshelfItem] = list()

        soup = bs(response.text, "html.parser")

        article_list = soup.find("div", {"class": "article-list"})
        if not article_list: return resultList, False
        for article in article_list.find_all("a", {"class": "article-item-inner"}):
            resultList.append(BookshelfItem(
                href = article['href'],
                title = article.find("div", {"class": "primary-info"}).text.strip("\n\t "),
                last_update = article.find("div", {"class": "date-info"}).text.strip("\n\t "),
            ))

        return resultList, self.has_next_page(soup, self.NEW_VERSION)
    
    @staticmethod
    def has_next_page(soup: bs, new_version: bool = False):
        has_next_page = True
        if new_version:
            pages_list = soup.find("div", {"class": "g-pager"})
            if not pages_list: 
                return False
            
            for a in pages_list.find_all("a"):
                if a.has_attr("class") and "mode-active" in a["class"]: 
                    has_next_page = False
                elif not has_next_page: 
                    has_next_page = True
                    break
        else:
            pages_list = soup.find("ul", {"class": "mode-paging"})
            if not pages_list: 
                return False

            for li in pages_list.find_all("li"):
                if li.has_attr("class") and "mode-paging-active" in li["class"]:
                    has_next_page = False
                elif not has_next_page:
                    has_next_page = True
                    break

        return has_next_page

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

            authors: list[Author] = list()
            if _filter != "articles":
                for author in manga_item.find_all("span", {"class": "manga-author-name"}):
                    if author.parent.name == "a":
                        if authors and authors[-1].href == author.parent["href"]:
                            authors[-1].name += author.text.strip('\t\n ')
                        else:
                            authors.append(Author(author.text.strip('\t\n '), author.parent["href"]))
                    else:
                        if authors:
                            if author.next_sibling and not author.next_sibling.text.strip('\t\n '):
                                authors[-1].name += author.text.strip('\t\n ')
                            elif not author.findNextSibling:
                                authors[-1].name += author.text.strip('\t\n ')
                            else:
                                authors.append(Author(author.text.strip('\t\n '), ""))
                        else:
                            authors.append(Author(author.text.strip('\t\n '), ""))
            else:
                authors.append(Author("", ""))

            title_h2 = manga_item.find("h2", {"class": "manga-title"})
            if title_h2.contents:
                title = title_h2.contents[-1].text.strip('\n\t ')
            else:
                title = title_h2.text.strip('\n\t ')
            
            resultList.append(MangaStoreItem(
                href=link["href"] if link.has_attr("href") else link['data-href'],
                title=title,
                author=authors,
            ))
        
        return resultList, ComiciClient.has_next_page(soup, self.NEW_VERSION)
    
    def _new_version_series_list_parse(self, soup: bs) -> list[MangaStoreItem]:
        series_list = soup.find("div", {"class": "series-list"})
        if not series_list: return list()

        resultList = list()
        for series in series_list.find_all("div", {"class": "series-list-item"}):
            item = series.find("a", {"class": "series-list-item-link"})
            authors_div = series.find("div", {"class": "series-list-item-author"})
            authors: list[Author] = [
                Author(
                    name = "".join(a.text.strip('\n\t ').split("\n")), 
                    href = urljoin(self.HOST, a["href"])
                ) for a in authors_div.find_all("a", {"class": "series-list-item-author-link"})
            ]

            resultList.append(MangaStoreItem(
                href = urljoin(self.HOST, item["href"]),
                title = item.find("img", {"class": "series-list-item-img"})['alt'],
                author = authors,
            ))

        return resultList
    
    def author(
        self,
        author_id: str,
        page: int = 0,
    ) -> tuple[list[MangaStoreItem], bool]: 
        response = self.main_client.get(
            urljoin(self.HOST, f"/authors/{author_id}"),
            params={
                "page": page if page >= 0 else 0,
            }
        )
        response.raise_for_status()

        resultList = list()

        soup = bs(response.text, "html.parser")

        if self.NEW_VERSION:
            resultList = self._new_version_series_list_parse(soup)
        else:
            series_list = soup.find("div", {"class": "authors-series-list"})
            if not series_list: return resultList, False

            for manga_store_item in series_list.find_all("div", {"class": "manga-store-item"}):
                link = manga_store_item.find("a")
                authors: list[Author] = list()
                author_div = manga_store_item.find("div", {"class": "author"})

                for author in author_div.find_all("a"):
                    authors.append(Author(author.text.strip('\t\n '), author["href"]))
                
                resultList.append(MangaStoreItem(
                    href=link["href"] if link.has_attr("href") else link['data-href'],
                    title=manga_store_item.find("div", {"class": "title-text"}).text.strip('\n\t '),
                    author=authors,
                ))
        
        return resultList, ComiciClient.has_next_page(soup, self.NEW_VERSION)
    
    def series_list(
        self,
        page: int = 0,
        sort: Literal["更新順", "新作順"] = "更新順",
    ) -> tuple[list[MangaStoreItem], bool]:
        
        if self.NEW_VERSION:
            page += 1
            response = self.main_client.get(
                urljoin(self.HOST, f"/series/list/{'up' if sort == '更新順' else 'new'}/{page}"),
            )
        else:
            response = self.main_client.get(
                urljoin(self.HOST, "/series/list"),
                params={
                    "page": page if page >= 0 else 0,
                    "sortType": "更新順" if sort == "更新順" else "新作順"
                }
            )
        response.raise_for_status()

        resultList: list[MangaStoreItem] = list()

        soup = bs(response.text, "html.parser")

        if self.NEW_VERSION:
            resultList = self._new_version_series_list_parse(soup)
        else:
            series_list = soup.find("div", {"class": "series-list"})
            if not series_list: return resultList, False
            for series in series_list.find_all("div", {"class": "series-box-vertical"}):
                article = series.find("div", {"class": "article-text"})
                title = article.find("h2", {"class": "title-text"}).text.strip('\n\t ')
                link = series.find("a")

                if link.has_attr("href"):
                    href = link["href"]
                elif link.has_attr("data-href"):
                    href = link['data-href']
                else:
                    href = ""

                authors: list[Author] = list()
                author_div = series.find("div", {"class": "author"})

                if len(author_div.contents) > 1:
                    for author in author_div.contents[1:]:
                        name = author.text.strip('\n\t ')
                        if not name: continue
                        if author.name == "a" and author.has_attr("href"): 
                            authors.append(Author(name.replace("\n", ""), author["href"]))
                        else:
                            if authors and authors[-1].name.endswith("/"):
                                authors[-1].name = authors[-1].name + name
                            else:
                                authors.append(Author(name, ""))

                resultList.append(MangaStoreItem(
                    href=href,
                    title=title,
                    author=authors
                ))

        return resultList, ComiciClient.has_next_page(soup, self.NEW_VERSION)
    
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
            },
            follow_redirects=True,
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

    def episodes(self, href: str | None = None, episode_id: str | None = None) -> tuple[str, str]:
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
            follow_redirects=True,
        )
        response.raise_for_status()

        soup = bs(response.text, "html.parser") 

        user_id = soup.find("span", {"id": "login_user_id"})
        if user_id: self.user_id = user_id.text

        comici_viewer = soup.find("div", {"id": "comici-viewer"})
        if not comici_viewer: return "", ""

        if comici_viewer.has_attr("comici-viewer-id"):
            return comici_viewer["comici-viewer-id"], comici_viewer.get("series-id", "")
        elif comici_viewer.has_attr("data-comici-viewer-id"): 
            return comici_viewer["data-comici-viewer-id"], comici_viewer.get("data-series-id", "")
        else: 
            return "", ""
    
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
    
    def book_contentsInfo(self, comici_viewer_id: str, page_from: int, page_to: int, user_id: int | str = "0") -> tuple[list[ContentsInfo], int]:
        response = self.main_client.get(
            urljoin(self.HOST, "/book/contentsInfo" if not self.NEW_VERSION else "/api/book/contentsInfo"),
            params={
                "user-id": user_id if user_id and str(user_id) != "0" else (self.user_id if self.user_id else "0"),
                "comici-viewer-id": comici_viewer_id,
                "page-from": page_from,
                "page-to": page_to
            }
        )
        response.raise_for_status()

        resJson = response.json()
        if not resJson.get("code", 1000) == 1000:
            raise Exception(resJson['message'])
        
        return [ContentsInfo(**r) for r in resJson["result"]], resJson.get("totalPages", 0)
    
    def api_user_info(self) -> tuple[str | None, str | None]:
        """Only avaliable for new version Comici, raise 403 if haven't login"""
        response = self.main_client.get(
            urljoin(self.HOST, "/api/user/info"),
        )
        response.raise_for_status()

        resJson = response.json()

        return resJson['user']['id'], resJson['user']['username']
    
    def api_popups(self) -> tuple[str | None, str | None]:
        """Only avaliable for new version Comici, safer than api_user_info"""
        response = self.main_client.get(
            urljoin(self.HOST, "/api/popups"),
        )
        response.raise_for_status()

        resJson = response.json()

        return resJson['topPopup'].get("userId"), resJson['topPopup'].get("userName")
    
    def api_bookshelf(self, page: int = 1, bookshelf_type: Literal["", "favorite", "buying", "liking"] = "") -> tuple[list[BookshelfItem], bool]:

        if bookshelf_type in ("buying", "liking"):
            raise Exception("Unsupported bookshelf type so far")
        
        self.user_id, user_name = self.api_popups()
        if not self.user_id or not user_name: 
            raise Exception("Cannot get user info")

        _new_type_match = {
            "": "/series/viewedHistory",
            "favorite": "/series/favorite",
            "buying": "/episodes/rentalHistories",
            "liking": "/episodes/liked"
        }
        if page < 1: page = 1

        response = self.main_client.get(
            urljoin(self.HOST, f"/api{_new_type_match[bookshelf_type]}"),
            params={
                "page": page,
            }
        )
        response.raise_for_status()

        _tag_match = {
            "": "viewedSeries",
            "favorite": "favoriteSeries",
            "buying": "episodeRentalHistories",
            "liking": "likedEpisodes"
        }

        resJson = response.json()
        lastPage = resJson['lastPage']
        
        resJson = resJson[_tag_match[bookshelf_type]]

        resultList = list()

        if resJson['totalCount'] == 0:
            return resultList, False

        if bookshelf_type in ("", "favorite"):
            for item in resJson[_tag_match[bookshelf_type]]:
                summary = item['seriesSummary']
                resultList.append(BookshelfItem(
                    href = urljoin(self.HOST, f"/series/{summary['id']}"),
                    title = summary['name'],
                    last_update = datetime.datetime.fromtimestamp(summary['updatedOn']).strftime("%Y/%m/%d %H:%M:%S")
                ))

        return resultList, lastPage > page
    
    @staticmethod
    def _authors_format(authors: list[dict]) -> list[Author]:
        return [
            Author(
                name=f"{author['role']}/{author['name']}" 
                        if author['role'] and len(authors) > 1
                        else author['name'], 
                href=author['authorPageLink']
            ) 
            for author in authors
        ]
    
    def api_series_access(
        self, 
        series_id: str, 
        episode_from: int = 1, 
        episode_to: int = 1
    ):
        response = self.main_client.get(
            urljoin(self.HOST, f"/api/series/access"),
            params={
                "seriesHash": series_id,
                "episodeFrom": episode_from,
                "episodeTo": episode_to
            }
        )
        response.raise_for_status()

        return response.json()
    
    def api_episodes(
        self,
        series_id: str,
        episode_from: int = 1,
        episode_to: int = 1,
    ):
        response = self.main_client.get(
            urljoin(self.HOST, f"/api/episodes"),
            params={
                "seriesHash": series_id,
                "episodeFrom": episode_from,
                "episodeTo": episode_to
            }
        )
        response.raise_for_status()

        return response.json()

    def new_series_summary(self, series_id: str) -> SeriesSummary:
        resJson = self.api_episodes(series_id)['series']['summary']
        return SeriesSummary(
            href = urljoin(self.HOST, f"/series/{resJson['id']}"),
            title = resJson['name'],
            author = ComiciClient._authors_format(resJson['author']),
            numEpisodes = resJson['numEpisodes'],
        )
    
    def new_series_pagingList(
        self, 
        series_id: str, 
        sort: int = 2, 
        page: int = 0, 
        limit: int = 30
    ) -> tuple[list[NewMangaEpisodeItem], bool]:
        '''通过新版API模仿传统访问'''
        summary = self.new_series_summary(series_id)
        low = page * limit + 1
        high = low + limit - 1

        if sort == 1:
            episode_from = summary.numEpisodes - high + 1
            episode_to = summary.numEpisodes - low + 1
        else:
            episode_from = low
            episode_to = high

        access = self.api_series_access(series_id, episode_from, episode_to)['seriesAccess']['episodeAccesses']
        info = self.api_episodes(series_id, episode_from, episode_to)['series']['episodes']

        resultList = list()
        for index, episode in enumerate(info):
            hasAccess = access[index]['hasAccess']
            resultList.append(NewMangaEpisodeItem(
                href = urljoin(self.HOST, f"/episodes/{episode['id']}"),
                title = episode['title'],
                update_date = datetime.datetime.fromtimestamp(episode['datePublished']).strftime("%Y-%m-%d %H:%M:%S"),
                symbols = ["HAS" if hasAccess else ""],
                hasAccess = hasAccess,
                accessType = access[index]['accessType'],
            ))

        return resultList, summary.numEpisodes > high
    
    def new_book_info_and_episode_info(self, series_id: str) -> tuple[Info, list[EpisodeInfo]]:
        resJson = self.api_episodes(
            series_id, 
            episode_from=1, 
            episode_to=self.new_series_summary(series_id).numEpisodes
        )['series']
        episodes = resJson['episodes'] if resJson['episodes'] else None

        summary = resJson['summary']

        return Info(
            _id = summary['id'],
            title = summary['name'],
            thumb_image_url = summary['images'][0]['url'] if summary['images'] else "",
            description = json.loads(summary['description'])[0]['children'][0]['text'] if summary['description'] else "",
            publish_date = datetime.datetime.fromtimestamp(summary['publishDate']).strftime("%Y-%m-%d %H:%M:%S"),
            end_date = None,
            authors = ComiciClient._authors_format(summary['author']),
        ), [EpisodeInfo(
            _id = episode['id'],
            name = episode['title'],
            description = "",
            thumb_image_url = episode['thumbnailImages'][0]['url'] if episode['thumbnailImages'] else "",
            page_count = "N/A",
            episode_number = i + 1,
            publish_date = datetime.datetime.fromtimestamp(episode['datePublished']).strftime("%Y-%m-%d %H:%M:%S"),
            end_date = None
        ) for i, episode in enumerate(episodes)] if episodes else None

    def api_search(
        self,
        keyword: str,
        page: int = 1,
        size: int = 24,
        _filter: Literal["series", "seriesofauthors", "articles"] = "series",
    ) -> tuple[list[MangaStoreItem], bool]:
        response = self.main_client.get(
            urljoin(self.HOST, f"/api/search"),
            params={
                "q": keyword,
                "page": page,
                "size": size
            }
        )
        response.raise_for_status()

        _filter_match = {
            "series": "series",
            "seriesofauthors": "seriesByAuthor",
            "articles": "episode"
        }

        resJson = response.json()
        resultList = list()
        
        for result in resJson['searchResult'][_filter_match[_filter]][_filter_match[_filter]]:
            resultList.append(MangaStoreItem(
                href = urljoin(self.HOST, f"/episodes/{result['id']}"),
                title = result['name'],
                author = ComiciClient._authors_format(result['authors'])
            ))

        return resultList, resJson['searchResult'][_filter_match[_filter]]['total'] > page * size
    
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