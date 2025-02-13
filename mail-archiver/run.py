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
        print(setting)
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

        mail = mailutils.connectToImapMailbox(setting.get('domain'), setting.get('username'), imapPassword, setting.get('ssl', True))
        mailfolders = mailutils.getMailFolders(setting, mail)
        print(mailfolders);
        # printImapFolders()

if __name__ == '__main__':
    archive()