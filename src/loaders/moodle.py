import json
import logging
import re
import tempfile
import unicodedata
import zipfile
from pathlib import Path

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
from src.loaders.models.book import Book, BookChapter
from src.loaders.models.coursetopic import CourseTopic
from src.loaders.models.folder import Folder
from src.loaders.models.glossary import Glossary, GlossaryEntry
from src.loaders.models.hp5activities import H5PActivities
from src.loaders.models.module import ModuleTypes, H5P_HANDLERS
from src.loaders.models.moodlecourse import MoodleCourse
from src.loaders.models.resource import Resource
from src.loaders.models.videotime import Video, VideoPlatforms
from src.loaders.audio import Audio
from src.loaders.pdf import PDF
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
        # Cache für Module-Intros: {coursemodule_id: intro_html}
        # Verschiedene Modultypen können intro haben, wird pro Kurs geladen
        self.module_intros_cache = {}

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
            
            # Lade alle Module-Intros für diesen Kurs (1x pro Kurs)
            self._load_module_intros_for_course(course.id)
            
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
                case ModuleTypes.GLOSSARY:
                    err_message = self.extract_glossary(module)
                case ModuleTypes.RESOURCE:
                    err_message = self.extract_resource(module)
                case ModuleTypes.FOLDER:
                    err_message = self.extract_folder(module)
                case ModuleTypes.BOOK:
                    err_message = self.extract_book(module)
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

    def extract_glossary(self, module):
        """
        Extrahiert Glossar-Einträge aus einem Moodle Glossary Modul.
        
        Verwendet module.instance (glossary_id) aus core_course_get_contents.
        
        Args:
            module: Module-Objekt mit modname="glossary" und instance=glossary_id
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        try:
            # module.instance enthält bereits die glossary_id von core_course_get_contents
            glossary_id = module.instance
            
            # API-Call für alle Glossar-Einträge
            caller = APICaller(
                url=self.api_endpoint,
                params=self.function_params,
                wsfunction="mod_glossary_get_entries_by_letter",
                id=glossary_id,
                letter="ALL",  # Alle Einträge
                **{"from": 0, "limit": 1000}  # Max 1000 Einträge
            )
            
            response = caller.getJSON()
            
            # Parse Response
            entries_data = response.get("entries", [])
            total_count = response.get("count", 0)
            
            if not entries_data:
                self.logger.info(f"Glossary {glossary_id} (Module {module.id}) hat keine Einträge")
                return None
            
            # Erstelle GlossaryEntry Objekte (nur concept + definition relevant)
            entries = []
            for entry_data in entries_data:
                try:
                    entry = GlossaryEntry(
                        id=entry_data["id"],
                        concept=entry_data["concept"],
                        definition=entry_data["definition"]
                    )
                    entries.append(entry)
                except Exception as e:
                    self.logger.warning(f"Fehler beim Parsen von Glossary Entry {entry_data.get('id')}: {e}")
                    continue
            
            # Erstelle Glossary-Objekt und befülle Module
            module.glossary = Glossary(
                glossary_id=glossary_id,
                module_id=module.id,
                entries=entries
            )
            
            self.logger.info(f"Glossary {glossary_id} erfolgreich geladen: {len(entries)}/{total_count} Einträge")
            return None
            
        except Exception as e:
            error_msg = f"Fehler beim Laden von Glossary {module.id}: {str(e)}"
            self.logger.error(error_msg)
            return error_msg

    def extract_resource(self, module):
        """
        Extrahiert Inhalte aus einem Resource-Modul.
        
        Kann mehrere Dateien enthalten - alle werden verarbeitet und kombiniert.
        
        Args:
            module: Module-Objekt mit modname="resource" und contents mit Dateien
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        try:
            if not module.contents or len(module.contents) == 0:
                self.logger.warning(f"Resource-Modul {module.id} hat keine Dateiinhalte")
                return None
            
            # Hole Intro-Text aus Cache (wurde pro Kurs geladen)
            intro_html = self.module_intros_cache.get(module.id, "")
            self.logger.info(
                f"Intro für Modul {module.id}: "
                f"{'GEFUNDEN (' + str(len(intro_html)) + ' Zeichen)' if intro_html else 'NICHT IM CACHE'}"
            )
            intro_text = self._extract_intro_text(intro_html, module.id)
            
            # Sammle extrahierte Texte aller Dateien
            all_extracted_texts = []
            if intro_text:
                all_extracted_texts.append(f"Intro:\n{intro_text}")
            
            # Verarbeite jede Datei im Resource-Modul
            for idx, file_content in enumerate(module.contents):
                self.logger.info(
                    f"Verarbeite Datei {idx+1}/{len(module.contents)} in Resource-Modul {module.id}: "
                    f"{file_content.filename}"
                )
                
                # Bereinige mimetype (entferne Query-Parameter wie "?forcedownload=1")
                mimetype = file_content.type.split('?')[0] if file_content.type else None
                if not mimetype:
                    self.logger.warning(f"Datei {file_content.filename} hat keinen Dateityp")
                    continue
                
                # Erstelle Resource-Objekt
                resource = Resource(
                    filename=file_content.filename,
                    fileurl=file_content.fileurl,
                    mimetype=mimetype,
                    filesize=file_content.filesize if hasattr(file_content, 'filesize') else None
                )
                
                # Prüfe Unterstützung
                if not resource.is_supported:
                    self.logger.info(
                        f"Datei {resource.filename} hat nicht-unterstützten Dateityp: {resource.mimetype}"
                    )
                    continue
                
                # Download Datei
                caller = APICaller(url=file_content.fileurl, params=self.download_params)
                caller.get()
                file_bytes = caller.response.content
                
                if not file_bytes:
                    self.logger.error(f"Konnte {resource.filename} nicht herunterladen")
                    continue
                
                # Extrahiere Text (Logik in Resource-Klasse)
                extracted_text = resource.extract_from_bytes(file_bytes, self.logger)
                
                if extracted_text:
                    # Bei mehreren Dateien: Header hinzufügen
                    if len(module.contents) > 1:
                        all_extracted_texts.append(f"\n--- Datei: {resource.filename} ---\n{extracted_text}")
                    else:
                        all_extracted_texts.append(extracted_text)
            
            # Kombiniere alle Texte und speichere in module.resource
            if all_extracted_texts:
                combined_resource = Resource(
                    filename=f"{len(module.contents)} Dateien" if len(module.contents) > 1 else module.contents[0].filename,
                    fileurl=module.contents[0].fileurl,
                    mimetype="multi" if len(module.contents) > 1 else module.contents[0].type.split('?')[0],
                    extracted_text='\n'.join(all_extracted_texts)
                )
                module.resource = combined_resource
                self.logger.info(
                    f"Resource-Modul {module.id} erfolgreich verarbeitet: "
                    f"{len(module.contents)} Datei(en), {len(combined_resource.extracted_text)} Zeichen gesamt"
                )
            
            return None
            
        except Exception as e:
            error_msg = f"Fehler beim Laden von Resource {module.id}: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def extract_folder(self, module):
        """
        Extrahiert Inhalte aus einem Folder-Modul.
        
        Folder-Module enthalten mehrere Dateien - alle werden verarbeitet und kombiniert.
        Funktioniert analog zu extract_resource(), da beide ein contents-Array haben.
        
        Args:
            module: Module-Objekt mit modname="folder" und contents mit Dateien
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        try:
            if not module.contents or len(module.contents) == 0:
                self.logger.warning(f"Folder-Modul {module.id} hat keine Dateiinhalte")
                return None
            
            # Hole Intro-Text aus Cache (wurde pro Kurs geladen)
            intro_html = self.module_intros_cache.get(module.id, "")
            self.logger.info(
                f"Intro für Folder-Modul {module.id}: "
                f"{'GEFUNDEN (' + str(len(intro_html)) + ' Zeichen)' if intro_html else 'NICHT IM CACHE'}"
            )
            intro_text = self._extract_intro_text(intro_html, module.id)
            
            # Sammle extrahierte Dateien
            extracted_files: list[Resource] = []
            all_extracted_texts = []
            
            if intro_text:
                all_extracted_texts.append(intro_text)
            
            # Verarbeite jede Datei im Folder
            for idx, file_content in enumerate(module.contents):
                self.logger.info(
                    f"Verarbeite Datei {idx+1}/{len(module.contents)} in Folder-Modul {module.id}: "
                    f"{file_content.filename}"
                )
                
                # Bereinige mimetype (entferne Query-Parameter wie "?forcedownload=1")
                mimetype = file_content.type.split('?')[0] if file_content.type else None
                if not mimetype:
                    self.logger.warning(f"Datei {file_content.filename} hat keinen Dateityp")
                    continue
                
                # Erstelle Resource-Objekt
                resource = Resource(
                    filename=file_content.filename,
                    fileurl=file_content.fileurl,
                    mimetype=mimetype,
                    filesize=file_content.filesize if hasattr(file_content, 'filesize') else None
                )
                
                # Prüfe Unterstützung (PDF, Audio, ZIP, TXT, HTML)
                if not resource.is_supported:
                    self.logger.info(
                        f"Datei {resource.filename} hat nicht-unterstützten Dateityp: {resource.mimetype}"
                    )
                    continue
                
                # Download Datei
                caller = APICaller(url=file_content.fileurl, params=self.download_params)
                caller.get()
                file_bytes = caller.response.content
                
                if not file_bytes:
                    self.logger.error(f"Konnte {resource.filename} nicht herunterladen")
                    continue
                
                # Extrahiere Text (Logik in Resource-Klasse)
                extracted_text = resource.extract_from_bytes(file_bytes, self.logger)
                
                if extracted_text:
                    # Speichere Resource mit extrahiertem Text
                    resource.extracted_text = extracted_text
                    extracted_files.append(resource)
                    
                    # Bei mehreren Dateien: Header hinzufügen
                    if len(module.contents) > 1:
                        all_extracted_texts.append(f"\n--- Datei: {resource.filename} ---\n{extracted_text}")
                    else:
                        all_extracted_texts.append(extracted_text)
            
            # Erstelle Folder-Objekt und speichere in module.folder
            if extracted_files:
                combined_folder = Folder(
                    folder_id=module.instance,
                    module_id=module.id,
                    files=extracted_files,
                    combined_text='\n'.join(all_extracted_texts)
                )
                module.folder = combined_folder
                self.logger.info(
                    f"Folder-Modul {module.id} erfolgreich verarbeitet: "
                    f"{len(extracted_files)} Datei(en), {combined_folder.total_extracted_chars} Zeichen gesamt"
                )
            
            return None
            
        except Exception as e:
            error_msg = f"Fehler beim Laden von Folder {module.id}: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def extract_book(self, module):
        """
        Extrahiert Inhalte aus einem Book-Modul.
        
        Books enthalten Kapitel mit HTML-Inhalten, Videos und Anhängen.
        Verwendet die gleiche Logik wie extract_page() für HTML-Parsing und Video-Extraktion.
        
        Args:
            module: Module-Objekt mit modname="book" und contents mit Kapiteln
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        try:
            if not module.contents or len(module.contents) == 0:
                self.logger.warning(f"Book-Modul {module.id} hat keine Inhalte")
                return None
            
            # Hole Intro-Text aus Cache (wurde pro Kurs geladen)
            intro_html = self.module_intros_cache.get(module.id, "")
            self.logger.info(
                f"Intro für Book-Modul {module.id}: "
                f"{'GEFUNDEN (' + str(len(intro_html)) + ' Zeichen)' if intro_html else 'NICHT IM CACHE'}"
            )
            intro_text = self._extract_intro_text(intro_html, module.id)
            
            # Gruppiere contents nach Kapiteln (filepath)
            # Format: /287/ -> Kapitel 287
            chapters_data = {}
            structure_json = None
            
            for content in module.contents:
                # Structure-Content (JSON mit Kapitel-Hierarchie)
                if content.type == "content" and content.filename == "structure":
                    try:
                        structure_json = json.loads(content.content) if hasattr(content, 'content') else None
                    except json.JSONDecodeError:
                        self.logger.warning(f"Konnte structure.json für Book {module.id} nicht parsen")
                    continue
                
                # Ignoriere Dateien ohne fileurl
                if not content.fileurl:
                    continue
                
                # Extrahiere chapter_id aus fileurl
                # Format: https://moodle.ki-campus.org/webservice/pluginfile.php/40628/mod_book/chapter/287/index.html
                # -> chapter_id = "287"
                import re
                chapter_match = re.search(r'/chapter/(\d+)/', content.fileurl)
                if not chapter_match:
                    self.logger.debug(f"Konnte chapter_id nicht aus URL extrahieren: {content.fileurl}")
                    continue
                
                chapter_id = chapter_match.group(1)
                
                # Initialisiere Kapitel-Dict
                if chapter_id not in chapters_data:
                    chapters_data[chapter_id] = {
                        'title': None,
                        'html_url': None,
                        'html_content': None,
                        'attachments': []
                    }
                
                # index.html = Kapitel-Inhalt
                if content.filename == "index.html":
                    chapters_data[chapter_id]['html_url'] = content.fileurl
                    # content-Feld enthält oft den Titel
                    if hasattr(content, 'content') and content.content:
                        chapters_data[chapter_id]['title'] = content.content
                # Andere Dateien = Anhänge (PDFs, ZIPs, etc.)
                elif content.filename != "index.html":
                    chapters_data[chapter_id]['attachments'].append(content)
            
            self.logger.info(f"Book {module.id}: {len(chapters_data)} Kapitel gefunden")
            
            # Verarbeite jedes Kapitel
            book_chapters = []
            for chapter_id, data in sorted(chapters_data.items()):
                chapter_title = data['title'] or f"Kapitel {chapter_id}"
                self.logger.info(f"Verarbeite Kapitel '{chapter_title}' (ID: {chapter_id})")
                
                # Erstelle Chapter-Objekt
                chapter = BookChapter(
                    chapter_id=chapter_id,
                    title=chapter_title
                )
                
                # Extrahiere HTML-Text und Videos (wie bei PAGE)
                if data['html_url']:
                    html_text, transcripts, err = self._extract_html_content(data['html_url'], module.id)
                    chapter.html_text = html_text
                    chapter.transcripts = transcripts
                    
                    if err:
                        self.logger.warning(f"Fehler beim HTML-Parsing in Kapitel {chapter_id}: {err}")
                
                # Verarbeite Anhänge (PDFs, ZIPs, etc.)
                for attachment_content in data['attachments']:
                    # Bereinige mimetype
                    mimetype = attachment_content.type.split('?')[0] if attachment_content.type else None
                    if not mimetype:
                        continue
                    
                    # Erstelle Resource-Objekt
                    resource = Resource(
                        filename=attachment_content.filename,
                        fileurl=attachment_content.fileurl,
                        mimetype=mimetype,
                        filesize=attachment_content.filesize if hasattr(attachment_content, 'filesize') else None
                    )
                    
                    # Nur unterstützte Formate verarbeiten
                    if not resource.is_supported:
                        self.logger.debug(f"Anhang {resource.filename} hat nicht-unterstützten Typ: {resource.mimetype}")
                        continue
                    
                    # Download und Extraktion
                    try:
                        caller = APICaller(url=attachment_content.fileurl, params=self.download_params)
                        caller.get()
                        file_bytes = caller.response.content
                        
                        if file_bytes:
                            extracted_text = resource.extract_from_bytes(file_bytes, self.logger)
                            if extracted_text:
                                resource.extracted_text = extracted_text
                                chapter.attachments.append(resource)
                    except Exception as e:
                        self.logger.warning(f"Fehler beim Download von {resource.filename}: {e}")
                
                book_chapters.append(chapter)
            
            # Erstelle Book-Objekt
            if book_chapters:
                book = Book(
                    book_id=module.instance,
                    module_id=module.id,
                    intro=intro_text if intro_text else None,
                    chapters=book_chapters,
                    structure=structure_json
                )
                module.book = book
                
                self.logger.info(
                    f"Book-Modul {module.id} erfolgreich verarbeitet: "
                    f"{book.total_chapters} Kapitel, {book.total_videos} Videos, {book.total_attachments} Anhänge"
                )
            
            return None
            
        except Exception as e:
            error_msg = f"Fehler beim Laden von Book {module.id}: {str(e)}"
            self.logger.error(error_msg)
            return error_msg
    
    def _extract_html_content(self, html_url: str, module_id: int) -> tuple[str | None, list, str | None]:
        """
        Extrahiert HTML-Text und Videos aus einer HTML-URL.
        
        Verwendet die gleiche Logik wie extract_page() für HTML-Parsing und Video-Extraktion.
        
        Args:
            html_url: URL der HTML-Datei
            module_id: Module-ID für Logging
            
        Returns:
            tuple: (html_text, transcripts, error_message)
        """
        err_message = None
        transcripts = []
        html_text = None
        
        try:
            page_content_caller = APICaller(url=html_url, params=self.download_params)
            soup = BeautifulSoup(page_content_caller.getText(), "html.parser")
            
            # Extrahiere Text
            if soup.text is not None:
                html_text = soup.get_text("\n")
                # Normalize parsed text (remove \xa0 from str)
                html_text = unicodedata.normalize("NFKD", html_text)
            
            # Extrahiere Videos aus Links (wie bei PAGE)
            links = soup.find_all("a")
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
                        transcripts.append(texttrack)
                    elif src.find("youtu") != -1:
                        try:
                            videotime = Video(id=0, vimeo_url=src)
                        except ValidationError:
                            self.logger.warning(f"Cannot parse video url: {src}")
                            continue
                        if videotime.video_id is None:
                            # Link refers not to a specific video, but to a channel overview page
                            continue
                        else:
                            youtube = Youtube()
                            texttrack, err_message = youtube.get_transcript(videotime.video_id)
                            transcripts.append(texttrack)
        
        except ParserRejectedMarkup:
            self.logger.warning(f"HTML-Parser rejected markup für Modul {module_id}")
        except Exception as e:
            err_message = f"Fehler beim HTML-Parsing: {str(e)}"
            self.logger.error(err_message)
        
        return html_text, transcripts, err_message
    
    def _load_module_intros_for_course(self, course_id: int):
        """
        Lädt alle Module-Intros für einen Kurs in den Cache.
        
        core_course_get_contents gibt das intro-Feld nicht zurück, daher müssen wir
        die modulspezifischen APIs nutzen (z.B. mod_resource_get_resources_by_courses).
        
        Aktuell werden nur Resource-Intros geladen. Kann erweitert werden für:
        - mod_glossary_get_glossaries_by_courses
        - mod_page_get_pages_by_courses
        - etc.
        
        Args:
            course_id: ID des Kurses
        """
        try:
            # Lade alle Resource-Module des Kurses mit ihren Intros
            self.logger.info(f"Lade Resource-Intros für Kurs {course_id}...")
            caller = APICaller(
                url=self.api_endpoint,
                params={**self.function_params, "courseids[0]": course_id},
                wsfunction="mod_resource_get_resources_by_courses"
            )
            response = caller.getJSON()
            resources = response.get("resources", [])
            
            self.logger.info(f"API-Antwort: {len(resources)} Resources gefunden")
            
            # Speichere intro pro coursemodule_id im Cache
            for resource in resources:
                coursemodule_id = resource.get("coursemodule")
                intro_html = resource.get("intro", "")
                if coursemodule_id:
                    self.module_intros_cache[coursemodule_id] = intro_html
                    self.logger.debug(
                        f"  - Modul {coursemodule_id}: Intro mit {len(intro_html)} Zeichen"
                    )
            
            self.logger.info(f"Kurs {course_id}: {len(resources)} Resource-Intros in Cache gespeichert")
            self.logger.debug(f"Cache enthält jetzt {len(self.module_intros_cache)} Einträge gesamt")
            
            # Lade Folder-Intros
            self.logger.info(f"Lade Folder-Intros für Kurs {course_id}...")
            folder_caller = APICaller(
                url=self.api_endpoint,
                params={**self.function_params, "courseids[0]": course_id},
                wsfunction="mod_folder_get_folders_by_courses"
            )
            folder_response = folder_caller.getJSON()
            folders = folder_response.get("folders", [])
            
            for folder in folders:
                coursemodule_id = folder.get("coursemodule")
                intro_html = folder.get("intro", "")
                if coursemodule_id:
                    self.module_intros_cache[coursemodule_id] = intro_html
                    self.logger.debug(
                        f"  - Modul {coursemodule_id}: Intro mit {len(intro_html)} Zeichen"
                    )
            
            self.logger.info(f"Kurs {course_id}: {len(folders)} Folder-Intros in Cache gespeichert")
            self.logger.debug(f"Cache enthält jetzt {len(self.module_intros_cache)} Einträge gesamt")
            
            # Lade Book-Intros
            self.logger.info(f"Lade Book-Intros für Kurs {course_id}...")
            book_caller = APICaller(
                url=self.api_endpoint,
                params={**self.function_params, "courseids[0]": course_id},
                wsfunction="mod_book_get_books_by_courses"
            )
            book_response = book_caller.getJSON()
            books = book_response.get("books", [])
            
            for book in books:
                coursemodule_id = book.get("coursemodule")
                intro_html = book.get("intro", "")
                if coursemodule_id:
                    self.module_intros_cache[coursemodule_id] = intro_html
                    self.logger.debug(
                        f"  - Modul {coursemodule_id}: Intro mit {len(intro_html)} Zeichen"
                    )
            
            self.logger.info(f"Kurs {course_id}: {len(books)} Book-Intros in Cache gespeichert")
            self.logger.debug(f"Cache enthält jetzt {len(self.module_intros_cache)} Einträge gesamt")
            
            # Hier können weitere Modultypen hinzugefügt werden:
            # - mod_glossary_get_glossaries_by_courses
            # - mod_page_get_pages_by_courses
            # etc.
            
        except Exception as e:
            self.logger.warning(f"Fehler beim Laden der Module-Intros für Kurs {course_id}: {e}")
    
    def _extract_intro_text(self, intro_html: str | None, module_id: int) -> str:
        """
        Extrahiert und bereinigt Intro-Text aus HTML.
        
        Args:
            intro_html: HTML-String mit Intro-Text
            module_id: Module-ID für Logging
            
        Returns:
            str: Bereinigter Text oder leerer String
        """
        if not intro_html:
            return ""
        
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(intro_html, "html.parser")
            text = soup.get_text("\n")
            text = unicodedata.normalize("NFKD", text)
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            return text + "\n\n" if text else ""
        except Exception as e:
            self.logger.warning(f"Fehler beim Parsen des Intro-Texts für Modul {module_id}: {e}")
            return ""

if __name__ == "__main__":
    moodle = Moodle()
    courses = moodle.extract()
