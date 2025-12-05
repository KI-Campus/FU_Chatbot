import json
import logging
import re
import tempfile
import unicodedata
import zipfile

from bs4 import BeautifulSoup, ParserRejectedMarkup
from llama_index.core import Document
from pydantic import ValidationError

from src.env import env
from src.loaders.APICaller import APICaller
from src.loaders.failed_transcripts import (
    FailedCourse,
    FailedModule,
    FailedTranscripts,
    save_failed_transcripts_to_excel,
)
from src.loaders.models.coursetopic import CourseTopic
from src.loaders.models.hp5activities import H5PActivities
from src.loaders.models.module import ModuleTypes, H5P_HANDLERS
from src.loaders.models.moodlecourse import MoodleCourse
from src.loaders.models.videotime import Video, VideoPlatforms
from src.loaders.vimeo import Vimeo
from src.loaders.youtube import Youtube


class Moodle:
    """class for Moodle API clients
    base_url: base url of moodle instance
    token: token for moodle api"""
    
    def __init__(self) -> None:
        self.logger = logging.getLogger("loader")
        self.base_url = env.DATA_SOURCE_MOODLE_URL
        self.api_endpoint = f"{self.base_url}webservice/rest/server.php"
        self.token = env.DATA_SOURCE_MOODLE_TOKEN
        self.function_params = {
            "wstoken": self.token,
            "moodlewsrestformat": "json",
        }
        self.download_params = {
            "token": self.token,
            "forcedownload": 1,
        }

    def get_courses(self) -> list[MoodleCourse]:
        """get all courses that are set to visible on moodle"""
        caller = APICaller(
            url=self.api_endpoint,
            params=self.function_params,
            wsfunction="core_course_get_courses",
        )
        courses = caller.getJSON()
        course_url = self.base_url + "course/view.php?id="
        courses = [MoodleCourse(url=course_url, **course) for course in courses if course["visible"] == 1]

        return courses

    def get_course_contents(self, course_id: int) -> list[CourseTopic]:
        """get all contents/topics/modules of a course"""
        course_contents_caller = APICaller(
            url=self.api_endpoint,
            params=self.function_params,
            wsfunction="core_course_get_contents",
            courseid=course_id,
        )
        course_contents = course_contents_caller.getJSON()
        course_contents = [CourseTopic(**topic) for topic in course_contents]
        return course_contents

    def get_h5p_module_ids(self, course_id: int) -> list[H5PActivities]:
        h5p_activities: list[H5PActivities] = []
        h5p_module_ids_caller = APICaller(
            url=self.api_endpoint,
            params={**self.function_params, "courseids[0]": course_id},
            wsfunction="mod_h5pactivity_get_h5pactivities_by_courses",
        )
        ids_json = h5p_module_ids_caller.getJSON()
        h5p_activities = [H5PActivities(**activity) for activity in ids_json["h5pactivities"]]
        return h5p_activities

    def get_videotime_content(self, cmid: int):
        caller = APICaller(
            url=self.api_endpoint,
            params=self.function_params,
            wsfunction="mod_videotime_get_videotime",
            cmid=cmid,
        )
        videotime_content = caller.getJSON()
        return videotime_content

    def extract(self) -> list[Document]:
        """extracts all courses and their contents from moodle"""

        failedTranscripts: FailedTranscripts = FailedTranscripts(courses=[])

        courses = self.get_courses()
        for i, course in enumerate(courses):
            self.logger.debug(f"Processing course id: {course.id}, course {i+1}/{len(courses)}")
            course.topics = self.get_course_contents(course.id)
            h5p_activity_ids = self.get_h5p_module_ids(course.id)
            for topic in course.topics:
                failed_modules = self.get_module_contents(topic, h5p_activity_ids)
                if failed_modules:
                    failedTranscripts.courses.append(FailedCourse(course=course, modules=failed_modules))

        course_documents = [doc for course in courses for doc in course.to_document()]
        course_documents.append(self.get_toc_document(courses))
        save_failed_transcripts_to_excel(transcripts=failedTranscripts, file_name="FailedTranscripts.xlsx")
        return course_documents

    def get_toc_document(self, courses) -> Document:
        toc_str = "List of all available courses:\n"
        for course in courses:
            toc_str += f"Course ID: {course.id}, Course Name: {course.fullname}\n"

        metadata = {
            "fullname": "Table of Contents",
            "type": "toc",
            "url": "https://ki-campus.org/overview/course",
        }

        toc_doc = Document(text=toc_str, metadata=metadata)

        return toc_doc

    def get_module_contents(self, topic, h5p_activities):
        failed_modules: list[FailedModule] = []

        for module in topic.modules:
            err_message = None
            if module.visible == 0:
                continue
            match module.type:
                case ModuleTypes.VIDEOTIME:
                    err_message = self.extract_videotime(module)
                case ModuleTypes.PAGE:
                    err_message = self.extract_page(module)
                case ModuleTypes.H5P:
                    for activity in h5p_activities:
                        if activity.coursemodule == module.id:
                            err_message = self.extract_h5p(module, activity)
            if err_message:
                failed_modules.append(FailedModule(modul=module, err_message=err_message))

        return failed_modules

    def extract_page(self, module):
        err_message = None

        for content in module.contents:
            if content.type in ["gif?forcedownload=1", "png?forcedownload=1"]:
                continue
            page_content_caller = APICaller(url=content.fileurl, params=self.download_params)
            try:
                soup = BeautifulSoup(page_content_caller.getText(), "html.parser")
            except ParserRejectedMarkup:
                continue
            links = soup.find_all("a")

            if soup.text is not None:
                module.text = soup.get_text("\n")
                # Normalize parsed text (remove \xa0 from str)
                module.text = unicodedata.normalize("NFKD", module.text)

            for p_link in links:
                pattern = r"https://player\.vimeo\.com/video/\d+"
                match = re.search(pattern, str(p_link))
                src = match.group(0) if match else p_link.get("href")
                if src:
                    if src.find("vimeo") != -1:
                        videotime = Video(id=0, vimeo_url=src)
                        if videotime.video_id is None:
                            self.logger.warning(f"Cannot parse video url: {src}")
                            continue
                        vimeo = Vimeo()
                        texttrack, err_message = vimeo.get_transcript(videotime.video_id)
                    elif src.find("youtu") != -1:
                        try:
                            videotime = Video(id=0, vimeo_url=src)
                        except ValidationError:
                            self.logger.warning(f"Cannot parse video url: {src}")
                            continue
                        if videotime.video_id is None:
                            # Link refers not to a specific video, but to a channel overview page
                            texttrack = None
                        else:
                            youtube = Youtube()
                            texttrack, err_message = youtube.get_transcript(videotime.video_id)
                    else:
                        texttrack = None
                    module.transcripts.append(texttrack)
        return err_message if err_message is not None else None

    def extract_videotime(self, module):  # TODO: rename method
        videotime = Video(**self.get_videotime_content(module.id))

        err_message = None

        if videotime.video_id is None:
            return

        match videotime.type:
            case VideoPlatforms.VIMEO:
                vimeo = Vimeo()
                texttrack, err_message = vimeo.get_transcript(videotime.video_id)
                module.transcripts.append(texttrack)
            case VideoPlatforms.YOUTUBE:
                youtube = Youtube()
                texttrack, err_message = youtube.get_transcript(videotime.video_id)
                module.transcripts.append(texttrack)
            case VideoPlatforms.SELF_HOSTED:
                # found no subtitles in self-hosted videos, if this ever changes add code here
                pass

        return err_message if err_message is not None else None

    # A H5P Module is a zipped bundle of js, css and a content.json, describing the content.
    # If a video is wrapped in a H5P Module we are only interested in the content.json.
    # In the content.json we find the link to the video. Based on that link we can construct
    # the link to the transcript of that video. Then we download that transcript and add it to the
    # module.transcripts list.
    def extract_h5p(self, module, activity):
        """Extrahiert H5P-Inhalte und routet zu entsprechender Klasse."""
        h5pfile_call = APICaller(url=activity.fileurl, params=self.download_params)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            # H5P-Package herunterladen
            local_filename = h5pfile_call.getFile(activity.filename, tmp_dir)
            
            # h5p.json für library-Feld extrahieren
            with zipfile.ZipFile(local_filename, "r") as zip_ref:
                zip_ref.extract("h5p.json", tmp_dir)
                zip_ref.extract("content/content.json", tmp_dir)
            
            # Lade h5p.json für library-Informationen
            h5p_json = f"{tmp_dir}/h5p.json"
            with open(h5p_json, "r") as json_file:
                h5p_data = json.load(json_file)
            
            # Lade content.json für eigentliche Inhalte
            content_json = f"{tmp_dir}/content/content.json"
            with open(content_json, "r") as json_file:
                content = json.load(json_file)
            
            # H5P Content-Typ aus h5p.json extrahieren (nicht content.json!)
            library = h5p_data.get("mainLibrary", "") or h5p_data.get("preloadedDependencies", [{}])[0].get("machineName", "")
            if not library:
                self.logger.error(f"Kein library-Feld in h5p.json für Modul {module.id}")
                return "Kein library-Feld in h5p.json gefunden"
            
            module.h5p_content_type = library
            self.logger.info(f"Verarbeite H5P-Typ: {library} für Modul {module.id}")
            
            # Finde passenden Handler im Mapping
            handler_class_path = None
            for h5p_type, class_path in H5P_HANDLERS.items():
                if h5p_type in library:
                    handler_class_path = class_path
                    break
            
            if not handler_class_path:
                self.logger.warning(f"H5P-Typ '{library}' wird noch nicht unterstützt (Modul {module.id})")
                return f"H5P-Typ '{library}' wird noch nicht unterstützt"
            
            # Dynamisch Handler-Klasse importieren
            module_path, class_name = handler_class_path.rsplit(".", 1)
            handler_module = __import__(module_path, fromlist=[class_name])
            handler_class = getattr(handler_module, class_name)
            
            self.logger.info(f"Rufe Handler {class_name} auf für Modul {module.id}")
            
            # Rufe from_h5p_package direkt auf (befüllt module und gibt error zurück)
            err = handler_class.from_h5p_package(
                module=module,
                content=content,
                h5p_zip_path=local_filename,
                vimeo_service=Vimeo(),
                video_service=Video
            )
            
            if err:
                self.logger.error(f"Fehler beim Verarbeiten von Modul {module.id}: {err}")
            else:
                self.logger.info(f"Modul {module.id} erfolgreich verarbeitet")
            
            return err
        
        return None


if __name__ == "__main__":
    moodle = Moodle()
    courses = moodle.extract()
