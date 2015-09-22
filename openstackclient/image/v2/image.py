#   Copyright 2012-2013 OpenStack Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

"""Image V2 Action Implementations"""

import argparse
import logging
import six

from cliff import command
from cliff import lister
from cliff import show

from glanceclient.common import utils as gc_utils
from openstackclient.api import utils as api_utils
from openstackclient.common import exceptions
from openstackclient.common import parseractions
from openstackclient.common import utils
from openstackclient.identity import common


class AddProjectToImage(show.ShowOne):
    """Associate project with image"""

    log = logging.getLogger(__name__ + ".AddProjectToImage")

    def get_parser(self, prog_name):
        parser = super(AddProjectToImage, self).get_parser(prog_name)
        parser.add_argument(
            "image",
            metavar="<image>",
            help="Image to share (name or ID)",
        )
        parser.add_argument(
            "project",
            metavar="<project>",
            help="Project to associate with image (name or ID)",
        )
        common.add_project_domain_option_to_parser(parser)
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        image_client = self.app.client_manager.image
        identity_client = self.app.client_manager.identity

        project_id = common.find_project(identity_client,
                                         parsed_args.project,
                                         parsed_args.project_domain).id

        image_id = utils.find_resource(
            image_client.images,
            parsed_args.image).id

        image_member = image_client.image_members.create(
            image_id,
            project_id,
        )

        return zip(*sorted(six.iteritems(image_member._info)))


class DeleteImage(command.Command):
    """Delete image(s)"""

    log = logging.getLogger(__name__ + ".DeleteImage")

    def get_parser(self, prog_name):
        parser = super(DeleteImage, self).get_parser(prog_name)
        parser.add_argument(
            "images",
            metavar="<image>",
            nargs="+",
            help="Image(s) to delete (name or ID)",
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        image_client = self.app.client_manager.image
        for image in parsed_args.images:
            image_obj = utils.find_resource(
                image_client.images,
                image,
            )
            image_client.images.delete(image_obj.id)


class ListImage(lister.Lister):
    """List available images"""

    log = logging.getLogger(__name__ + ".ListImage")

    def get_parser(self, prog_name):
        parser = super(ListImage, self).get_parser(prog_name)
        public_group = parser.add_mutually_exclusive_group()
        public_group.add_argument(
            "--public",
            dest="public",
            action="store_true",
            default=False,
            help="List only public images",
        )
        public_group.add_argument(
            "--private",
            dest="private",
            action="store_true",
            default=False,
            help="List only private images",
        )
        public_group.add_argument(
            "--shared",
            dest="shared",
            action="store_true",
            default=False,
            help="List only shared images",
        )
        parser.add_argument(
            '--property',
            metavar='<key=value>',
            action=parseractions.KeyValueAction,
            help='Filter output based on property',
        )
        parser.add_argument(
            '--long',
            action='store_true',
            default=False,
            help='List additional fields in output',
        )

        # --page-size has never worked, leave here for silent compatibility
        # We'll implement limit/marker differently later
        parser.add_argument(
            "--page-size",
            metavar="<size>",
            help=argparse.SUPPRESS,
        )
        parser.add_argument(
            '--sort',
            metavar="<key>[:<direction>]",
            help="Sort output by selected keys and directions(asc or desc) "
                 "(default: asc), multiple keys and directions can be "
                 "specified separated by comma",
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        image_client = self.app.client_manager.image

        kwargs = {}
        if parsed_args.public:
            kwargs['public'] = True
        if parsed_args.private:
            kwargs['private'] = True
        if parsed_args.shared:
            kwargs['shared'] = True

        if parsed_args.long:
            columns = (
                'ID',
                'Name',
                'Disk Format',
                'Container Format',
                'Size',
                'Status',
                'visibility',
                'protected',
                'owner',
                'tags',
            )
            column_headers = (
                'ID',
                'Name',
                'Disk Format',
                'Container Format',
                'Size',
                'Status',
                'Visibility',
                'Protected',
                'Owner',
                'Tags',
            )
        else:
            columns = ("ID", "Name")
            column_headers = columns

        # List of image data received
        data = []
        # No pages received yet, so start the page marker at None.
        marker = None
        while True:
            page = image_client.api.image_list(marker=marker, **kwargs)
            if not page:
                break
            data.extend(page)
            # Set the marker to the id of the last item we received
            marker = page[-1]['id']

        if parsed_args.property:
            # NOTE(dtroyer): coerce to a list to subscript it in py3
            attr, value = list(parsed_args.property.items())[0]
            api_utils.simple_filter(
                data,
                attr=attr,
                value=value,
                property_field='properties',
            )

        data = utils.sort_items(data, parsed_args.sort)

        return (
            column_headers,
            (utils.get_dict_properties(
                s,
                columns,
                formatters={
                    'tags': utils.format_dict,
                },
            ) for s in data)
        )


class RemoveProjectImage(command.Command):
    """Disassociate project with image"""

    log = logging.getLogger(__name__ + ".RemoveProjectImage")

    def get_parser(self, prog_name):
        parser = super(RemoveProjectImage, self).get_parser(prog_name)
        parser.add_argument(
            "image",
            metavar="<image>",
            help="Image to unshare (name or ID)",
        )
        parser.add_argument(
            "project",
            metavar="<project>",
            help="Project to disassociate with image (name or ID)",
        )
        common.add_project_domain_option_to_parser(parser)
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        image_client = self.app.client_manager.image
        identity_client = self.app.client_manager.identity

        project_id = common.find_project(identity_client,
                                         parsed_args.project,
                                         parsed_args.project_domain).id

        image_id = utils.find_resource(
            image_client.images,
            parsed_args.image).id

        image_client.image_members.delete(image_id, project_id)


class SaveImage(command.Command):
    """Save an image locally"""

    log = logging.getLogger(__name__ + ".SaveImage")

    def get_parser(self, prog_name):
        parser = super(SaveImage, self).get_parser(prog_name)
        parser.add_argument(
            "--file",
            metavar="<filename>",
            help="Downloaded image save filename (default: stdout)",
        )
        parser.add_argument(
            "image",
            metavar="<image>",
            help="Image to save (name or ID)",
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        image_client = self.app.client_manager.image
        image = utils.find_resource(
            image_client.images,
            parsed_args.image,
        )
        data = image_client.images.data(image.id)

        gc_utils.save_image(data, parsed_args.file)


class ShowImage(show.ShowOne):
    """Display image details"""

    log = logging.getLogger(__name__ + ".ShowImage")

    def get_parser(self, prog_name):
        parser = super(ShowImage, self).get_parser(prog_name)
        parser.add_argument(
            "image",
            metavar="<image>",
            help="Image to display (name or ID)",
        )
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)

        image_client = self.app.client_manager.image
        image = utils.find_resource(
            image_client.images,
            parsed_args.image,
        )

        info = {}
        info.update(image)
        return zip(*sorted(six.iteritems(info)))


class SetImage(show.ShowOne):
    """Set image properties"""

    log = logging.getLogger(__name__ + ".SetImage")
    deadopts = ('size', 'store', 'location', 'copy-from', 'checksum')

    def get_parser(self, prog_name):
        parser = super(SetImage, self).get_parser(prog_name)
        # TODO(bunting): There are additional arguments that v1 supported
        # --size - does not exist in v2
        # --store - does not exist in v2
        # --location - maybe location add?
        # --copy-from - does not exist in v2
        # --file - should be able to upload file
        # --volume - needs adding
        # --force - needs adding
        # --checksum - maybe could be done client side
        # --stdin - could be implemented
        # --property - needs adding
        # --tags - needs adding
        parser.add_argument(
            "image",
            metavar="<image>",
            help="Image to modify (name or ID)"
        )
        parser.add_argument(
            "--name",
            metavar="<name>",
            help="New image name"
        )
        parser.add_argument(
            "--architecture",
            metavar="<architecture>",
            help="Operating system Architecture"
        )
        protected_group = parser.add_mutually_exclusive_group()
        protected_group.add_argument(
            "--protected",
            action="store_true",
            help="Prevent image from being deleted"
        )
        protected_group.add_argument(
            "--unprotected",
            action="store_true",
            help="Allow image to be deleted (default)"
        )
        public_group = parser.add_mutually_exclusive_group()
        public_group.add_argument(
            "--public",
            action="store_true",
            help="Image is accessible to the public",
        )
        public_group.add_argument(
            "--private",
            action="store_true",
            help="Image is inaccessible to the public (default)",
        )
        parser.add_argument(
            "--instance-uuid",
            metavar="<instance_uuid>",
            help="ID of instance used to create this image"
        )
        parser.add_argument(
            "--min-disk",
            type=int,
            metavar="<disk-gb>",
            help="Minimum disk size needed to boot image, in gigabytes"
        )
        visibility_choices = ["public", "private"]
        public_group.add_argument(
            "--visibility",
            metavar="<visibility>",
            choices=visibility_choices,
            help=argparse.SUPPRESS
        )
        help_msg = ("ID of image in Glance that should be used as the kernel"
                    " when booting an AMI-style image")
        parser.add_argument(
            "--kernel-id",
            metavar="<kernel-id>",
            help=help_msg
        )
        parser.add_argument(
            "--os-version",
            metavar="<os-version>",
            help="Operating system version as specified by the distributor"
        )
        disk_choices = ["None", "ami", "ari", "aki", "vhd", "vmdk", "raw",
                        "qcow2", "vdi", "iso"]
        help_msg = ("Format of the disk. Valid values: %s" % disk_choices)
        parser.add_argument(
            "--disk-format",
            metavar="<disk-format>",
            choices=disk_choices,
            help=help_msg
        )
        parser.add_argument(
            "--os-distro",
            metavar="<os-distro>",
            help="Common name of operating system distribution"
        )
        parser.add_argument(
            "--owner",
            metavar="<owner>",
            help="New Owner of the image"
        )
        msg = ("ID of image stored in Glance that should be used as the "
               "ramdisk when booting an AMI-style image")
        parser.add_argument(
            "--ramdisk-id",
            metavar="<ramdisk-id>",
            help=msg
        )
        parser.add_argument(
            "--min-ram",
            type=int,
            metavar="<ram-mb>",
            help="Amount of RAM (in MB) required to boot image"
        )
        container_choices = ["None", "ami", "ari", "aki", "bare", "ovf", "ova"]
        help_msg = ("Format of the container. Valid values: %s"
                    % container_choices)
        parser.add_argument(
            "--container-format",
            metavar="<container-format>",
            choices=container_choices,
            help=help_msg
        )
        for deadopt in self.deadopts:
            parser.add_argument(
                "--%s" % deadopt,
                metavar="<%s>" % deadopt,
                dest=deadopt.replace('-', '_'),
                help=argparse.SUPPRESS
            )
        return parser

    def take_action(self, parsed_args):
        self.log.debug("take_action(%s)", parsed_args)
        image_client = self.app.client_manager.image

        for deadopt in self.deadopts:
            if getattr(parsed_args, deadopt.replace('-', '_'), None):
                raise exceptions.CommandError(
                    "ERROR: --%s was given, which is an Image v1 option"
                    " that is no longer supported in Image v2" % deadopt)

        kwargs = {}
        copy_attrs = ('architecture', 'container_format', 'disk_format',
                      'file', 'kernel_id', 'locations', 'name',
                      'min_disk', 'min_ram', 'name', 'os_distro', 'os_version',
                      'owner', 'prefix', 'progress', 'ramdisk_id',
                      'visibility')
        for attr in copy_attrs:
            if attr in parsed_args:
                val = getattr(parsed_args, attr, None)
                if val:
                    # Only include a value in kwargs for attributes that are
                    # actually present on the command line
                    kwargs[attr] = val

        # Handle exclusive booleans with care
        # Avoid including attributes in kwargs if an option is not
        # present on the command line.  These exclusive booleans are not
        # a single value for the pair of options because the default must be
        # to do nothing when no options are present as opposed to always
        # setting a default.
        if parsed_args.protected:
            kwargs['protected'] = True
        if parsed_args.unprotected:
            kwargs['protected'] = False
        if parsed_args.public:
            kwargs['visibility'] = 'public'
        if parsed_args.private:
            kwargs['visibility'] = 'private'

        if not kwargs:
            self.log.warning("No arguments specified")
            return {}, {}

        image = utils.find_resource(
            image_client.images, parsed_args.image)

        image = image_client.images.update(image.id, **kwargs)
        info = {}
        info.update(image)
        return zip(*sorted(six.iteritems(info)))
