from dataclasses import dataclass, asdict
import json, datetime

@dataclass
class MangaStoreItem:
    href: str
    title: str
    author: list[str]

@dataclass
class MangaEpisodeItem:
    href: str
    title: str
    update_date: str
    symbols: list[str]

@dataclass
class Info:
   _id: str
   title: str
   thumb_image_url: str
   description: str
   publish_date: str
   end_date: str
   authors: str | None

@dataclass
class EpisodeInfo:
    _id: str # == comici_viewer_id
    name: str
    description: str
    thumb_image_url: str
    page_count: str
    episode_number: str
    publish_date: datetime.datetime
    end_date: datetime.datetime

    def __post_init__(self):
        self.publish_date = datetime.datetime.fromisoformat(self.publish_date)
        self.end_date = datetime.datetime.fromisoformat(self.end_date)

@dataclass
class ContentsInfo:
    imageUrl: str
    scramble: list[int]
    sort: int
    width: int
    height: int
    expiresOn: datetime.datetime

    def __post_init__(self):
        self.scramble = json.loads(self.scramble)
        self.expiresOn = datetime.datetime.fromtimestamp(self.expiresOn / 1000)