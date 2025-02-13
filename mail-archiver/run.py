import os
import click
import yaml


def prepare_dirs(settings):
    settings['maildir'] = 'mailbox.%s@%s' % (settings.get('username'), settings.get('domain'))
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
def archive(config):
    """Initialize config."""
    settings = yaml.safe_load(config)
    for mailbox in settings:
        print(mailbox)
        setting = prepare_dirs(mailbox)

if __name__ == '__main__':
    archive()