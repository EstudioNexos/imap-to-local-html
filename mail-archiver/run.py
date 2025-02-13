import os
import click
import yaml
import getpass

from .utils import normalize, removeDir, copyDir, humansize, simplifyEmailHeader, slugify_safe, strftime
from .mailutils import *

def welcomeBanner():
    click.echo(click.style("### Welcome to Mail Archiver ###", fg='blue'))
    click.echo(click.style("Runtime Information " + sys.version, fg='blue'))
    click.echo(click.style("-" * 40, fg='blue'))


def prepare_dirs(settings):
    settings['maildir'] = '%s/mailbox.%s@%s' % (settings.get('output'), settings.get('username'), settings.get('domain'))
    if not os.path.exists(settings['maildir']):
        os.mkdir(settings['maildir'])
    settings['maildir_raw'] = "%s/raw" % settings['maildir']
    if not os.path.exists(settings['maildir_raw']):
        os.mkdir(settings['maildir_raw'])

    settings['maildir_result'] = "%s/html" % settings['maildir']
    if not os.path.exists(settings['maildir_result']):
        os.mkdir(settings['maildir_result'])
    return settings

def printMailFolders(allFolders, currentParent = '', intend = '  '):
    """
    Prints list of folders
    """

    if not currentParent:
        print("All folders")

    for folderID in allFolders:
        folder = allFolders[folderID]
        if folder["parent"] != currentParent:
            continue

        if allFolders[folderID]["selected"]:
            print("%s**%s (%s)" % (intend, allFolders[folderID]["title"], folderID))
        else:
            print("%s%s (%s)" % (intend, allFolders[folderID]["title"], folderID))
        printMailFolders(allFolders, folderID, intend + "    ")

def walkMailFolders(settings, mail, mailfolders):
    for folderID in mailfolders:
        if not mailfolders[folderID]["selected"]:
            continue

        print(("Getting messages from server from folder: %s.") % normalize(folderID, "utf7"))
        retries = 0
        getMessageToLocalDir(folderID, mail, settings['maildir_raw'])

        # try:
        # except imaplib.IMAP4_SSL.abort:
        #     if retries < 5:
        #         print(("SSL Connection Abort. Trying again (#%i).") % retries)
        #         retries += 1
        #         mail = mailutils.connectToImapMailbox(settings.get('domain'), settings.get('username'), imapPassword, settings.get('ssl', True))
        #         mailutils.getMessageToLocalDir(folderID, mail, settings['maildir_raw'])
        #     else:
        #         print("SSL Connection gave more than 5 errors. Not trying again")


        # if settings.get('ssl', True):
        #     try:
        #         mailutils.getMessageToLocalDir(folderID, mail, settings['maildir_raw'])
        #     except imaplib.IMAP4_SSL.abort:
        #         if retries < 5:
        #             print(("SSL Connection Abort. Trying again (#%i).") % retries)
        #             retries += 1
        #             mail = mailutils.connectToImapMailbox(settings.get('domain'), settings.get('username'), imapPassword, settings.get('ssl', True))
        #             mailutils.getMessageToLocalDir(folderID, mail, settings['maildir_raw'])
        #         else:
        #             print("SSL Connection gave more than 5 errors. Not trying again")
        # else:
        #     try:
        #         mailutils.getMessageToLocalDir(folderID, mail, settings['maildir_raw'])
        #     except imaplib.IMAP4.abort:
        #         if retries < 5:
        #             print(("Connection Abort. Trying again (#%i).") % retries)
        #             retries += 1
        #             mail = mailutils.connectToImapMailbox(settings.get('domain'), settings.get('username'), imapPassword)
        #             mailutils.getMessageToLocalDir(folderID, mail, settings['maildir_raw'])
        #         else:
        #             print("Connection gave more than 5 errors. Not trying again")

        print(("Done with folder: %s.") % normalize(folderID, "utf7"))


@click.command()
@click.argument('config', type=click.File('rb'))
@click.argument('output')
def archive(config, output):
    """Initialize config."""
    assets_location = "assets"
    settings = yaml.safe_load(config)
    for setting in settings:
        setting['assets_location'] = assets_location
        setting['output'] = output
        setting = prepare_dirs(setting)
        # print(setting)
        mail = None
        mailFolders = None
        
        attCount = 0
        lastAttName = ""
        att_count = 0
        last_att_filename = ""

        welcomeBanner()

        imapPassword = setting.get('password')
        if not imapPassword:
            click.echo(click.style("Enter {} @ {} password".format(setting.get('username'), setting.get('domain')), fg='red'))
            imapPassword = getpass.getpass()

        mail = connectToImapMailbox(setting.get('domain'), setting.get('username'), imapPassword, setting.get('ssl', True))
        mailfolders = getMailFolders(setting, mail)
        printMailFolders(mailfolders)
        walkMailFolders(setting, mail, mailfolders)
        # printImapFolders()
        renderIndexPage()

if __name__ == '__main__':
    archive()