# Copyright (c) 2016 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type.
"""
import pprint
import sgtk

from tank_vendor import six

HookBaseClass = sgtk.get_hook_baseclass()
p4_app = sgtk.platform.current_engine().apps.get("tk-multi-perforce")

# import ptvsd

# # Allow other computers to attach to ptvsd at this IP address and port.
# ptvsd.enable_attach(address=('localhost', 5678), redirect_output=True)

class PerforceActions(HookBaseClass):
    """
    Stub implementation of the shell actions, used for testing.
    """

    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Return a list of action instances for a particular publish.
        This method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions menu for a publish.

        The mapping between Publish types and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the loader app
        has already established *which* actions are appropriate for this object.

        The hook should return at least one action for each item passed in via the
        actions parameter.

        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.

        Because you are operating on a particular publish, you may tailor the output
        (caption, tooltip etc) to contain custom information suitable for this publish.

        The ui_area parameter is a string and indicates where the publish is to be shown.
        - If it will be shown in the main browsing area, "main" is passed.
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed.

        Please note that it is perfectly possible to create more than one action "instance" for
        an action! You can for example do scene introspection - if the action passed in
        is "character_attachment" you may for example scan the scene, figure out all the nodes
        where this object can be attached and return a list of action instances:
        "attach to left hand", "attach to right hand" etc. In this case, when more than
        one object is returned for an action, use the params key to pass additional
        data into the run_action hook.

        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption and description
        """
        app = self.parent
        app.log_debug(
            "Generate actions called for UI element %s. "
            "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data)
        )

        action_instances = HookBaseClass.generate_actions(self, sg_publish_data, actions, ui_area)

        # For the sake of easy test, we'll reuse Maya publish types.

        if "perforce_sync" in actions:
            action_instances.append(
                {
                    "name": "perforce_sync",
                    "params": "Perforce Sync 'params'",
                    "caption": "Perforce: Sync",
                    "description": "Executes Perforce Sync.",
                }
            )

        return action_instances

    def execute_multiple_actions(self, actions):
        """
        Executes the specified action on a list of items.

        The default implementation dispatches each item from ``actions`` to
        the ``execute_action`` method.

        The ``actions`` is a list of dictionaries holding all the actions to execute.
        Each entry will have the following values:

            name: Name of the action to execute
            sg_publish_data: Publish information coming from Shotgun
            params: Parameters passed down from the generate_actions hook.

        .. note::
            This is the default entry point for the hook. It reuses the ``execute_action``
            method for backward compatibility with hooks written for the previous
            version of the loader.

        .. note::
            The hook will stop applying the actions on the selection if an error
            is raised midway through.

        :param list actions: Action dictionaries.
        """
        app = self.parent
        app.log_info("Executing action '%s' on the selection")
        # Helps to visually scope selections
        # Execute each action.
        perforce_entities = []
        perforce_type = None
        for single_action in actions:
            name = single_action["name"]
            sg_publish_data = single_action["sg_publish_data"]

            # If we're doing perforce sync, find all the selected entities instead of calling individually
            if name == "perforce_sync":
                if perforce_type == None:
                    perforce_type = sg_publish_data['type']
                elif perforce_type != sg_publish_data['type']:
                    # We can't run multiple types of entities together
                    raise Exception("Attempting to Perforce sync multiple entity types at once.")
                perforce_entities.append(sg_publish_data['id'])
                continue

            params = single_action["params"]
            HookBaseClass.execute_action(self, name, params, sg_publish_data)

        # Call perforce sync
        if perforce_type and len(perforce_entities):
            p4_app.sync_files(perforce_type, perforce_entities)
          
            
