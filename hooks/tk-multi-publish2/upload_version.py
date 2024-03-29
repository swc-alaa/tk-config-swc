# Copyright (c) 2017 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

import pprint
from shutil import copyfile
import subprocess
import tempfile
import sgtk
import os
import datetime
import re

HookBaseClass = sgtk.get_hook_baseclass()
TK_FRAMEWORK_SWC_NAME = "tk-framework-swc_v0.x.x"

class UploadVersionPlugin(HookBaseClass):
    @property
    def icon(self):
        """
        Path to an png icon on disk
        """

        # look for icon one level up from this hook's folder in "icons" folder
        return os.path.join(self.disk_location, os.curdir, "icons", "review.png")

    @property
    def name(self):
        """
        One line display name describing the plugin
        """
        return "Upload for review"

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """
        publisher = self.parent

        shotgun_url = publisher.sgtk.shotgun_url

        media_page_url = "%s/page/media_center" % (shotgun_url,)
        mobile_url = "https://help.autodesk.com/view/SGSUB/ENU/?guid=SG_Supervisor_Artist_sa_mobile_review_html"
        rv_url = "https://help.autodesk.com/view/SGSUB/ENU/?guid=SG_RV_rv_manuals_rv_easy_setup_html"

        return """
        Upload the file to ShotGrid for review.<br><br>

        A <b>Version</b> entry will be created in ShotGrid and a transcoded
        copy of the file will be attached to it. The file can then be reviewed
        via the project's <a href='%s'>Media</a> page, <a href='%s'>RV</a>, or
        the <a href='%s'>ShotGrid Review</a> mobile app.
        """ % (
            media_page_url,
            rv_url,
            mobile_url,
        )

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to recieve
        through the settings parameter in the accept, validate, publish and
        finalize methods.
        A dictionary on the following form::
            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }
        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """
        return {
            "File Extensions": {
                "type": "str",
                "default": "jpeg, jpg, png, mov, mp4, pdf, avi, wav, mp3",
                "description": "File Extensions of files to include",
            },
            "Upload": {
                "type": "bool",
                "default": True,
                "description": "Upload content to ShotGrid?",
            },
            "Link Local File": {
                "type": "bool",
                "default": True,
                "description": "Should the local file be referenced by ShotGrid",
            },
        }    

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.
        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["maya.*", "file.maya"]
        """

        # we use "video" since that's the mimetype category.
        return ["file.image", "file.video", "file.audio", "review.*"]

    def accept(self, settings, item):
        p4_data = item.properties.get("p4_data")
        if p4_data: 
            if p4_data["action"] == "delete":
                return {"accepted": False}
    
        if item.type_spec.split(".")[1] == "audio":
            if "_raw" in item.properties["path"]:
                return {"accepted": False}
        
        # get the base settings
        settings = super(UploadVersionPlugin, self).accept(settings, item)

        if(item.type_spec in ["file.image", "file.video"]):
            # set the default checked state
            settings["checked"] = False

        return settings

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish.
        Returns a boolean to indicate validity.
        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """
        publish_name = item.properties.get("publish_name")
        if not publish_name:
            version_path = self.get_next_version_name(item,item.properties["path"])
            version_path_components = self.publisher.util.get_file_path_components(version_path)
            publish_name = version_path_components["filename"]  
            
            self.logger.info("Using prior version info to determine publish version.")

            self.logger.info("Publish name: %s" % (publish_name,))  
            item.properties["publish_name"] = publish_name       
            item.name = f"(Review) {publish_name}"  
        return super(UploadVersionPlugin, self).validate(settings, item)

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.
        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent
        path = item.properties["path"]

        path_components = publisher.util.get_file_path_components(path)

        if path_components["filename"] != item.properties["publish_name"]:
            temp_path = os.path.join(
                    tempfile.gettempdir(), item.properties["publish_name"]
                )         
            copyfile(path, temp_path)
            item.properties["original_path"] = path
            item.properties["path"] = temp_path

        if item.type_spec.split(".")[1] == "audio":
            try:
                input_path = temp_path.replace("\\","/")
                encoded_mp4 = f'{os.path.splitext(item.properties["path"])[0]}.mp4'.replace("\\","/")
                # encoded_thumbnail = f'{os.path.splitext(item.properties["path"])[0]}.jpg'.replace("\\","/")
                # TODO: Make this program call more abstract in both location and OS
                subprocess.check_output(f'b:/Tools/Programs/ffmpeg/bin/ffmpeg.exe -y -i "{input_path}" -filter_complex "[0:a]showwaves=s=1280x720:mode=line,format=yuv420p[v]" -map "[v]" -map 0:a -c:v libx264 -c:a aac -b:a 160k "{encoded_mp4}"', shell=True, env={'PATH': os.getenv('PATH')})
                item.properties["sg_uploaded_movie_mp4"] = f'{os.path.splitext(item.properties["path"])[0]}.mp4'
                # subprocess.check_output(f'ffmpeg.exe -y -i "{input_path}" -filter_complex "showwavespic=s=640x240:split_channels=1" -frames:v 1 "{encoded_thumbnail}"', shell=True, env={'PATH': os.getenv('PATH')})
                # item.set_thumbnail_from_path(encoded_thumbnail)
                # item.properties["custom_thumbnail"] = encoded_thumbnail
            except Exception as e:
                self.logger.info("Audio conversion error.")

        """
        Executes the publish logic for the given item and settings.
        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        publisher = self.parent
        path = item.properties["path"]

        # allow the publish name to be supplied via the item properties. this is
        # useful for collectors that have access to templates and can determine
        # publish information about the item that doesn't require further, fuzzy
        # logic to be used here (the zero config way)
        publish_name = item.properties.get("publish_name")
        if not publish_name:

            self.logger.debug("Using path info hook to determine publish name.")

            # use the path's filename as the publish name
            path_components = publisher.util.get_file_path_components(path)
            publish_name = path_components["filename"]

        self.logger.debug("Publish name: %s" % (publish_name,))

        self.logger.info("Creating Version...")
        version_data = {
            "project": item.context.project,
            "code": publish_name,
            "description": item.description,
            "entity": self._get_version_entity(item),
            "sg_task": item.context.task,
        }

        if "sg_publish_data" in item.properties:
            publish_data = item.properties["sg_publish_data"]
            version_data["published_files"] = [publish_data]

        if settings["Link Local File"].value:
            version_data["sg_path_to_movie"] = path

        # log the version data for debugging
        self.logger.debug(
            "Populated Version data...",
            extra={
                "action_show_more_info": {
                    "label": "Version Data",
                    "tooltip": "Show the complete Version data dictionary",
                    "text": "<pre>%s</pre>" % (pprint.pformat(version_data),),
                }
            },
        )

        # Create the version
        version = publisher.shotgun.create("Version", version_data)
        self.logger.info("Version created!")

        # stash the version info in the item just in case
        item.properties["sg_version_data"] = version

        thumb = item.get_thumbnail_as_path()

        if settings["Upload"].value:
            self.logger.info("Uploading content...")

            # on windows, ensure the path is utf-8 encoded to avoid issues with
            # the shotgun api
            if sgtk.util.is_windows():
                upload_path = str.encode(path)
            else:
                upload_path = path

            if "sg_uploaded_movie_mp4" in item.properties:
                if sgtk.util.is_windows():
                    mp4_upload_path = str.encode(item.properties["sg_uploaded_movie_mp4"])
                else:
                    mp4_upload_path = item.properties["sg_uploaded_movie_mp4"]                
                self.parent.shotgun.upload(
                    "Version", version["id"], mp4_upload_path, "sg_uploaded_movie_mp4"
                )
                self.logger.info("Uploading thumbnail...")
                self.parent.shotgun.upload_thumbnail("Version", version["id"], thumb)   
                os.remove(item.properties["sg_uploaded_movie_mp4"])          
            else:
                self.parent.shotgun.upload(
                    "Version", version["id"], upload_path, "sg_uploaded_movie"
                )
        elif thumb:
            # only upload thumb if we are not uploading the content. with
            # uploaded content, the thumb is automatically extracted.
            self.logger.info("Uploading thumbnail...")
            self.parent.shotgun.upload_thumbnail("Version", version["id"], thumb)

        self.logger.info("Upload complete!")


    def finalize(self, settings, item):
        """
        Execute the finalization pass. This pass executes once all the publish
        tasks have completed, and can for example be used to version up files.
        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # Increment version number based on how many versions
        self.publisher = self.parent
        path = item.properties["path"]
        version = item.properties["sg_version_data"]
        type_class = item.type_spec.split(".")[0] 

        if("original_path" in item.properties):
            original_path = item.properties["original_path"]
            os.remove(path)
        else:
            original_path = path

        if(type_class == "review"):
            context = None
            try:
                context = self.swc_fw.find_task_context(original_path)
            except(AttributeError):
                try:
                    self.swc_fw = self.load_framework(TK_FRAMEWORK_SWC_NAME)
                    context = self.swc_fw.find_task_context(original_path)
                except:
                    # This probably isn't a valid folder
                    pass
            except:
                pass
            if context:
                os.remove(original_path)

                self.logger.info(
                    "Review deleted after uploading for file: %s" % (original_path,),
                    extra={
                        "action_show_in_shotgun": {
                            "label": "Show Version",
                            "tooltip": "Reveal the version in ShotGrid.",
                            "entity": version,
                        }
                    },
                )        
            else:
                self.logger.info(
                    "Review uploaded for file: %s" % (original_path,),
                    extra={
                        "action_show_in_shotgun": {
                            "label": "Show Version",
                            "tooltip": "Reveal the version in ShotGrid.",
                            "entity": version,
                        }
                    },
                )      
        else:
            super(UploadVersionPlugin, self).finalize(settings, item)

    def get_next_version_name(self, item, path):
        # Increment version number based on how many versions
        self.publisher = self.parent

        # use the path's filename as the base publish name
        path_components = self.publisher.util.get_file_path_components(path)
        publish_name = path_components["filename"]

        # See how many prior versions there are
        filters = [
            ['entity', 'is', self._get_version_entity(item)]
        ]

        prior_versions = self.publisher.shotgun.find("Version",filters,['code'])      

        regex = r"(" + re.escape(publish_name.split('.')[0]) + r"){1}(\.v\d)?\.\w*$"

        x = [i for i in prior_versions if re.match(regex,i['code'])]   

        # Set the publish name of this item as the next version
        version_number = len(x)+1     
        version_path = self.publisher.util.get_version_path(path,version_number)

        return version_path      
