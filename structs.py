from dataclasses import dataclass, asdict
import json, datetime

@dataclass
class Author:
    name: str
    href: str

@dataclass
class MangaStoreItem:
    href: str
    title: str
    author: list[Author]

    def __post_init__(self):
        for i in range(len(self.author)):
            if isinstance(self.author[i], str):
                self.author[i] = Author(self.author[i], "")

@dataclass
class MangaEpisodeItem:
    href: str
    title: str
    update_date: str
    symbols: list[str]

@dataclass
class BookshelfItem:
    href: str
    title: str
    last_update: str

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
    end_date: datetime.datetime | None

    def __post_init__(self):
        self.publish_date = datetime.datetime.fromisoformat(self.publish_date) if self.publish_date else None
        self.end_date = datetime.datetime.fromisoformat(self.end_date) if self.end_date else None

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

@dataclass
class Tag:
    _id: str
    name: str

@dataclass
class SeriesSummary(MangaStoreItem):
    numEpisodes: int

@dataclass
class NewMangaEpisodeItem(MangaEpisodeItem):
    hasAccess: bool
    accessType: str