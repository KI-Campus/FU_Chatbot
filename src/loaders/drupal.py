import logging
import unicodedata
from datetime import datetime
from enum import Enum
from typing import List

import requests
from bs4 import BeautifulSoup
from llama_index.core import Document

from src.env import env


class PageTypes(Enum):
    """
    The different types of pages that can be found on ki-campus.org
    First element is the internal name of the page,
    second element is the human-readable and translated name of the page
    """

    COURSE = ("course", "Kurs")
    ABOUT_US = ("about_us", "Über uns")
    PAGE = ("page", "Seite")
    BLOGPOST = ("blogpost", "Blogpost")
    SPEZIAL = ("dvv_page", "Spezial")  # Spezial / Stadt Land DatenFluss


DRUPAL_API_BASE_URL = "https://ki-campus.org/jsonapi/node/"


class Drupal:
    def __init__(
        self, base_url: str = "", username: str = "", client_id: str = "", client_secret: str = "", grant_type: str = ""
    ) -> None:
        self.logger = logging.getLogger("loader")
        # This fixes very slow requests, IPV6 is not properly supported by the ki-campus.org server
        # https://stackoverflow.com/questions/62599036/python-requests-is-slow-and-takes-very-long-to-complete-http-or-https-request
        requests.packages.urllib3.util.connection.HAS_IPV6 = False

        self.oauth_token = self.get_oauth_token("https://ki-campus.org")
        if not self.oauth_token:
            # Ohne gültiges Token werden spätere Drupal-Requests vermutlich 401 liefern,
            # aber die Ingestion soll nicht komplett abbrechen.
            self.logger.warning("No Drupal OAuth token retrieved; Drupal content may not be fully loaded.")
        self.header = {
            "Authorization": f"Bearer {self.oauth_token}",
            "Accept": "application/vnd.api+json",
            "Accept-Language": "de",
        }

    def get_oauth_token(self, base_url: str):
        try:
            response = requests.post(
                f"{base_url}/oauth2/token",
                data={
                    "client_id": env.DRUPAL_CLIENT_ID,
                    "client_secret": env.DRUPAL_CLIENT_SECRET,
                    "username": env.DRUPAL_USERNAME,
                    "password": env.DRUPAL_PASSWORD,
                    "grant_type": env.DRUPAL_GRANT_TYPE,
                },
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as err:
            # Netzwerk-/Auth-Problem beim Abrufen des OAuth-Tokens – nur loggen,
            # damit die restliche Ingestion weiterlaufen kann.
            self.logger.warning(
                f"Failed to retrieve Drupal OAuth token from {base_url}: {err}"
            )
            return None

        try:
            token_json = response.json()
            return token_json.get("access_token")
        except ValueError as err:
            self.logger.warning(
                f"Failed to parse Drupal OAuth token response from {base_url} as JSON: {err}"
            )
            return None

    def extract(self):
        all_docs = []

        for type in PageTypes:
            all_docs += self.get_page_type(type)
        return all_docs

    def get_page_type(self, page_type: PageTypes) -> List[Document]:
        documents: list[Document] = []
        node = self.get_data(f"{DRUPAL_API_BASE_URL}{page_type.value[0]}")
        for i, page in enumerate(node):
            self.logger.debug(f"Processing {page_type.value[0]} number: {i+1}/{len(node)}")

            if page["attributes"]["status"]:
                metadata = {
                    "title": page["attributes"]["title"],
                    "source": "Drupal",
                    "type": f"{page_type.value[0]}",
                    "date_created": datetime.fromisoformat(page["attributes"]["created"]).strftime("%Y-%m-%d"),
                    "url": f"https://ki-campus.org/node/{page['attributes']['drupal_internal__nid']}",
                }

                if page.get("attributes", {}).get("field_moodle_course_id") is not None:
                    metadata["course_id"] = page["attributes"]["field_moodle_course_id"]

                documents.append(
                    Document(
                        metadata=metadata,
                        text=self.get_page_representation(page, page_type),
                    )
                )

        return documents

    def get_data(self, url: str):
        data = []

        while url:
            try:
                response = requests.get(url, headers=self.header)
                # harte Fehler (z.B. 5xx) hier abfangen, aber nicht gesamte Ingestion abbrechen
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.RequestException as err:
                self.logger.warning(f"Failed to retrieve Drupal data from {url}: {err}")
                break
            except ValueError as err:
                # JSON-Parsing fehlgeschlagen (z.B. HTML-Fehlerseite statt JSON)
                self.logger.warning(f"Failed to parse Drupal response from {url} as JSON: {err}")
                break

            data.extend(result.get("data", []))
            next_link = result.get("links", {}).get("next")
            url = next_link["href"] if next_link else None
        return data

    def get_page_paragraphs(self, page_id: str, page_type: PageTypes | str):
        try:
            if type(page_type) is PageTypes:
                response = requests.get(
                    f"{DRUPAL_API_BASE_URL}{page_type.value[0]}/{page_id}/field_paragraphs", headers=self.header
                )
            elif type(page_type) is str:
                response = requests.get(
                    f"{DRUPAL_API_BASE_URL}{page_type}/{page_id}/field_content_paragraphs", headers=self.header
                )
            else:
                raise Exception('Bad type: "page_type"')
            response.raise_for_status()
            paragraphs = response.json()
        except requests.exceptions.RequestException as err:
            self.logger.warning(
                f"Failed to retrieve Drupal paragraphs for page {page_id} ({page_type}): {err}"
            )
            return ""
        except ValueError as err:
            self.logger.warning(
                f"Failed to parse Drupal paragraphs response for page {page_id} ({page_type}) as JSON: {err}"
            )
            return ""

        _result = ""
        for d in paragraphs["data"]:
            if d["type"] in ["paragraph--simple_text", "paragraph--textblock", "paragraph--text_and_image"]:
                if d["attributes"].get("field_paragraph_title") is not None:
                    _result += d["attributes"]["field_paragraph_title"]
                    _result += "\n"

                if d["attributes"].get("field_paragraph_body") is not None:
                    _result += BeautifulSoup(d["attributes"]["field_paragraph_body"]["value"], "html.parser").getText()
                    _result += "\n\n"

        return _result

    def fetch_data(self, url):
        try:
            response = requests.get(url, headers=self.header)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as err:
            self.logger.warning(f"Failed to retrieve Drupal resource from {url}: {err}")
            return {}
        except ValueError as err:
            self.logger.warning(f"Failed to parse Drupal resource from {url} as JSON: {err}")
            return {}

    def process_lecture_books(self, page) -> str:
        lecture_books = page["relationships"]["field_lecture_books"]["data"]
        books_text = ""

        for lecture_book in lecture_books:
            lecture_book_url = f"{DRUPAL_API_BASE_URL}lecture_book/{lecture_book['id']}"
            chapter_data = self.fetch_data(lecture_book_url)
            books_text += self.process_chapters(chapter_data)
            pass

        return books_text

    def process_chapters(self, chapter_data) -> str:
        chapters = (
            chapter_data.get("data", {})
            .get("relationships", {})
            .get("field_lecture_chapters", {})
            .get("data", [])
        )
        chapters_text = ""

        for single_chapter in chapters:
            # Yes, its really called lecture_chaper
            chapter_url = f"{DRUPAL_API_BASE_URL}lecture_chaper/{single_chapter['id']}"
            lecture_data = self.fetch_data(chapter_url)

            chapters_text += self.process_lectures(lecture_data)

        return chapters_text

    def process_lectures(self, lecture_data) -> str:
        lectures = (
            lecture_data.get("data", {})
            .get("relationships", {})
            .get("field_lectures", {})
            .get("data", [])
        )
        lectures_text = ""

        for lecture in lectures:
            lectures_text += self.get_page_paragraphs(lecture["id"], "lecture")

        return lectures_text

    def get_page_representation(self, page, page_type: PageTypes):
        final_representations = ""

        match page_type:
            case PageTypes.PAGE | PageTypes.BLOGPOST:
                final_representations += self.get_basic_representation(page, page_type)

            case PageTypes.SPEZIAL:
                final_representations += self.get_basic_representation(page, page_type)
                final_representations += self.process_lecture_books(page)

            case _:
                description = ""
                if page.get("relationships", {}).get("field_description") is not None:
                    description = BeautifulSoup(
                        page["attributes"]["field_description"]["value"], "html.parser"
                    ).getText()
                paragraphs = self.get_page_paragraphs(page["id"], page_type)

                type = ""
                if page.get("attributes", {}).get("field_format") is not None:
                    type = f'{page_type.value[1]} Type: {self.get_course_type(page["attributes"]["field_format"])}'

                length = ""
                if page.get("attributes", {}).get("field_umfang") is not None:
                    length = f'{page_type.value[1]} Length: {page["attributes"]["field_umfang"]}'

                difficulty = ""
                if page.get("attributes", {}).get("field_level") is not None:
                    difficulty = f'{page_type.value[1]} Difficulty: {page["attributes"]["field_level"]}'

                language = ""
                if page.get("attributes", {}).get("field_course_language") is not None:
                    language = f'{page_type.value[1]} language code: {page["attributes"]["field_course_language"]}'

                topics = ""
                if page.get("relationships", {}).get("field_occupational_field", {}).get("data") is not None:
                    topics = f"{page_type.value[1]} Topic(s): {self.get_course_topic(page['relationships']['field_occupational_field']['data'])}"

                final_representations = f"""
                {page_type.value[1]} Title: {page["attributes"]["title"]}
                {page_type.value[1]} Description: {description}
                {type}
                {length}
                {difficulty}
                {language}
                {topics}

                {paragraphs}
                """

        # Normalize parsed text (remove \xa0 from str)
        final_representations = unicodedata.normalize("NFKD", final_representations)
        return final_representations

    def get_course_type(self, short_type: str):
        match short_type:
            case "mooc":
                return "Online-Kurse & MOOCs"
            case "blended":
                return "Blended Learning"
            case "micro":
                return "Micro Content"
            case "podcast":
                return "Podcasts"
            case "video":
                return "Lernvideos"
            case "paths":
                return "Lernpfade"
            case _:
                raise Exception(f"Bad type: {short_type}")

    def get_course_topic(self, topic_list: list):
        topics_str = ""

        for idx, topic in enumerate(topic_list):
            topic_data = self.fetch_data(
                f"https://ki-campus.org/jsonapi/taxonomy_term/occupational_field/{topic['id']}"
            )
            if (topic_data.get("data")) is not None:
                if idx != 0:
                    topics_str += ", "
                topics_str += f"{topic_data['data']['attributes']['name']}"

        return topics_str

    def get_basic_representation(self, page, page_type: PageTypes):
        final_representations = f"""
                    {page_type.value[1]} Title: {page["attributes"]["title"]}
                """
        if page["attributes"]["body"] is not None:
            content = BeautifulSoup(page["attributes"]["body"]["value"], "html.parser").getText()

            if content is not None:
                content_text = f"\n{page_type.value[1]} Content: {content}"
                final_representations += content_text

        return final_representations


if __name__ == "__main__":
    docs = Drupal().extract()
