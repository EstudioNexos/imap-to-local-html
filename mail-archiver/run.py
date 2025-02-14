import os
import click
import yaml
import getpass

# from .utils import normalize, removeDir, copyDir, humansize, simplify_emailheaders, slugify_safe, strftime
from .mailutils import *
from .templating import build_templates

def welcomeBanner():
    click.echo(click.style("### Welcome to Mail Archiver ###", fg='blue'))
    click.echo(click.style("Runtime Information " + sys.version, fg='blue'))
    click.echo(click.style("-" * 40, fg='blue'))


def prepare_dirs(settings):
    settings['maildir'] = settings.get('output') + '%s@%s' % (settings.get('username'), settings.get('domain'))
    if not os.path.exists(settings['maildir']):
        os.mkdir(settings['maildir'])
    settings['maildir_raw'] = "%s/raw" % settings['maildir']
    if not os.path.exists(settings['maildir_raw']):
        os.mkdir(settings['maildir_raw'])

    settings['maildir_result'] = "%s/html" % settings['maildir']
    if not os.path.exists(settings['maildir_result']):
        os.mkdir(settings['maildir_result'])

    return settings

def print_mailfolders(allFolders, currentParent = '', intend = '  '):
    """
    Prints list of folders
    """

    if not currentParent:
        print("All folders")

    for folder_id in allFolders:
        folder = allFolders[folder_id]
        if folder["parent"] != currentParent:
            continue

        if allFolders[folder_id]["selected"]:
            print("%s**%s (%s)" % (intend, allFolders[folder_id]["title"], folder_id))
        else:
            print("%s%s (%s)" % (intend, allFolders[folder_id]["title"], folder_id))
        print_mailfolders(allFolders, folder_id, intend + "    ")

def walk_mailfolders(settings, mail, mailfolders):
    for folder_id in mailfolders:
        if not mailfolders[folder_id]["selected"]:
            continue

        print(("Getting messages from server from folder: %s.") % normalize(folder_id, "utf7"))
        get_message_to_local(folder_id, mail, settings['maildir_raw'])

        # retries = 0
        # try:
        # except imaplib.IMAP4_SSL.abort:
        #     if retries < 5:
        #         print(("SSL Connection Abort. Trying again (#%i).") % retries)
        #         retries += 1
        #         mail = mailutils.connectToImapMailbox(settings.get('domain'), settings.get('username'), imap_password, settings.get('ssl', True))
        #         mailutils.get_message_to_local(folder_id, mail, settings['maildir_raw'])
        #     else:
        #         print("SSL Connection gave more than 5 errors. Not trying again")


        # if settings.get('ssl', True):
        #     try:
        #         mailutils.get_message_to_local(folder_id, mail, settings['maildir_raw'])
        #     except imaplib.IMAP4_SSL.abort:
        #         if retries < 5:
        #             print(("SSL Connection Abort. Trying again (#%i).") % retries)
        #             retries += 1
        #             mail = mailutils.connectToImapMailbox(settings.get('domain'), settings.get('username'), imap_password, settings.get('ssl', True))
        #             mailutils.get_message_to_local(folder_id, mail, settings['maildir_raw'])
        #         else:
        #             print("SSL Connection gave more than 5 errors. Not trying again")
        # else:
        #     try:
        #         mailutils.get_message_to_local(folder_id, mail, settings['maildir_raw'])
        #     except imaplib.IMAP4.abort:
        #         if retries < 5:
        #             print(("Connection Abort. Trying again (#%i).") % retries)
        #             retries += 1
        #             mail = mailutils.connectToImapMailbox(settings.get('domain'), settings.get('username'), imap_password)
        #             mailutils.get_message_to_local(folder_id, mail, settings['maildir_raw'])
        #         else:
        #             print("Connection gave more than 5 errors. Not trying again")

        print(("Done with folder: %s.") % normalize(folder_id, "utf7"))


@click.command()
@click.argument('config', type=click.File('rb'))
@click.argument('output')
def archive(config, output):
    """Initialize config."""
    assets_location = "assets"
    templates_location = "templates"
    settings = yaml.safe_load(config)
    current_dir = os.path.dirname(os.path.realpath(__file__))
    for setting in settings:
        setting['assets_location'] = "{}/{}/".format(current_dir, assets_location)
        setting['templates_location'] = "{}/{}/".format(current_dir, templates_location)
        setting['output'] = output
        setting['current_dir'] = current_dir

        setting = prepare_dirs(setting)
        # print(setting)
        # mail = None
        # mailFolders = None
        
        # attCount = 0
        # lastAttName = ""
        # att_count = 0
        # last_att_filename = ""

        welcomeBanner()

        # mail_retrieve()
        imap_password = setting.get('password')
        if not imap_password:
            click.echo(click.style("Enter {} @ {} password".format(setting.get('username'), setting.get('domain')), fg='red'))
            imap_password = getpass.getpass()

        click.echo(click.style("Connecting to server", fg='blue'))
        mail = connectToImapMailbox(setting.get('domain'), setting.get('username'), imap_password, setting.get('ssl', True))
        mailfolders = getMailFolders(setting, mail)
        print_mailfolders(mailfolders)
        click.echo(click.style("Start walking folders", fg='blue'))
        walk_mailfolders(setting, mail, mailfolders)
        click.echo(click.style("Star building templates", fg='blue'))
        build_templates(setting, mailfolders)

if __name__ == '__main__':
    archive()