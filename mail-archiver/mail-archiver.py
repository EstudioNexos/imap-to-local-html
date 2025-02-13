#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2013 Remy van Elst
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <http://www.gnu.org/licenses/>.

from bs4 import BeautifulSoup
import imaplib
import email
import mailbox
from email.utils import parsedate
import time
import re
from math import ceil
import os
import base64
import datetime
from quopri import decodestring
import getpass

from jinja2 import Environment
import hashlib
import sys
import yaml

from utils import normalize, removeDir, copyDir, humansize, simplify_emailheaders, slugify_safe, strftime
import mailutils

global server

server = {}
try:
    with open('imap-to-local-html.yml', 'r') as file:
        server = yaml.safe_load(file)
        server = server.get('settings')
except Exception as e:
    pass

if not server:
    print("No yml was found or is not valid, exiting. Please check README file or imap-to-local-html.samle.yml for more details")
    exit()

mail = None
mailFolders = None
inc_location = "assets"

maildir = 'mailbox.%s@%s' % (server.get('username'), server.get('domain'))
if not os.path.exists(maildir):
    os.mkdir(maildir)

maildir_raw = "%s/raw" % maildir
if not os.path.exists(maildir_raw):
    os.mkdir(maildir_raw)

maildir_result = "%s/html" % maildir
if not os.path.exists(maildir_result):
    os.mkdir(maildir_result)


def get_title(title = None):
    """
    Returns title for all pges
    """

    global server

    result = []
    if title:
        result.append(title)

    result.append('%s@%s' % (server.get('username'), server.get('domain')))
    result.append('IMAP to local HTML')

    return ' | '.join(result)


def renderTemplate(templateFrom, saveTo, **kwargs):
    """
    Helper function to render a tamplete with variables
    """
    global server

    templateContents = ''
    with open("templates/%s" % templateFrom, "r") as f:
        templateContents = f.read()

    env = Environment()
    env.filters["humansize"] = humansize
    env.filters["simplify_emailheaders"] = simplify_emailheaders
    env.filters["strftime"] = strftime
    env.filters["render_breadcrumbs"] = render_breadcrumbs

    template = env.from_string(templateContents)
    result = template.render(**kwargs)
    if saveTo:
        with open(saveTo, "w", encoding="utf-8") as f:
            if server.get('prettify', True):
                try:
                    soup = BeautifulSoup(result, "html.parser")
                    f.write(soup.prettify())
                # RecursionError: maximum recursion depth exceeded while calling a Python object
                # or any other case
                except Exception as e:
                    f.write(result)
            else:
                f.write(result)

    return result


def render_breadcrumbs(folder_id, linkPrefix):
    """
    Renders a breadcrump towards a folder
    """

    allFolders = getMailFolders()
    if not folder_id or not folder_id in allFolders:
        return ''

    folderList = []
    currentfolder_id = folder_id
    while currentfolder_id and currentfolder_id in allFolders:
        if allFolders[currentfolder_id]["selected"]:
            folderList.append((allFolders[currentfolder_id]["title"], allFolders[currentfolder_id]["link"]))
        else:
            folderList.append((allFolders[currentfolder_id]["title"], None))

        currentfolder_id = allFolders[currentfolder_id]["parent"]

    folderList = folderList[::-1]
    return renderTemplate(
        "folder-breadcrump.tpl",
        None,
        folderList=folderList,
        linkPrefix=linkPrefix,
    )

def renderMenu(selectedFolder = '', currentParent = '', linkPrefix = '.'):
    """
    Renders the menu on the left

    Expects: selected folder (id), currentParent (for recursion)
    """

    menuToShow = []
    folders = getMailFolders()
    for folder_id in folders:
        folder = folders[folder_id]
        if folder["parent"] != currentParent:
            continue

        menuToAdd = folder
        menuToAdd["children"] = renderMenu(
            selectedFolder=selectedFolder,
            currentParent=folder_id,
            linkPrefix=linkPrefix
        )
        menuToShow.append(menuToAdd)

    if len(menuToShow) <= 0:
        return ""

    menuToShow.sort(key=lambda val: val["title"])

    return renderTemplate(
        "nav-ul.tpl",
        None,
        menuToShow=menuToShow,
        linkPrefix=linkPrefix,
        selectedFolder=selectedFolder,
    )


def renderPage(saveTo, **kwargs):
    """
    HTML page wrapper

    Expects: title, contentZ
    """
    kwargs['title'] = get_title(kwargs.get('title'))
    kwargs['username'] = server.get('username')
    kwargs['linkPrefix'] = kwargs.get('linkPrefix', '.')
    kwargs['sidemenu'] = renderMenu(
        selectedFolder=kwargs.get('selectedFolder', ''),
        linkPrefix=kwargs['linkPrefix'],
    )

    if (kwargs.get("headerTitle")):
        kwargs['header'] = renderHeader(kwargs.get("headerTitle"))

    return renderTemplate("html.tpl", saveTo, **kwargs)


def renderHeader(title):
    """
    Renders a simple header

    Expects: title
    """

    return renderTemplate("header-main.tpl", None, title=title)


def renderThread(mailsPerID = {}, thread_current_mail_id = '', currently_selected_mail_id = '', linkPrefix = '.'):
    """
    Renders a thread of mails
    """

    if not thread_current_mail_id in mailsPerID:
        return ""

    mailToShow = []

    parentID = mailsPerID[thread_current_mail_id].get("parent")

    # if there is no parent, assume no other siblings
    if not parentID or not parentID in mailsPerID:
        threadCurrent = {
            "id": thread_current_mail_id,
            "link": mailsPerID[thread_current_mail_id].get("link"),
            "date": mailsPerID[thread_current_mail_id].get("date"),
            "subject": mailsPerID[thread_current_mail_id].get("subject", "(mail not found)"),
            "selected": thread_current_mail_id == currently_selected_mail_id,
        }

        mailToShow.append(threadCurrent)
    else:
        for siblingID in mailsPerID[parentID].get("children", []):
            if not siblingID in mailsPerID:
                threadCurrent = {
                    "id": thread_current_mail_id,
                    "link": None,
                    "date": None,
                    "subject": "(mail not found)",
                    "selected": siblingID == currently_selected_mail_id,
                }
                mailToShow.append(threadCurrent)
                continue

            threadCurrent = {
                "id": siblingID,
                "link": mailsPerID[siblingID]["link"],
                "date": mailsPerID[siblingID]["date"],
                "subject": mailsPerID[siblingID]["subject"],
                "selected": siblingID == currently_selected_mail_id,
            }

            mailToShow.append(threadCurrent)

    # For each sibling, go to first child and try to recurse
    for pos in range(len(mailToShow)):
        # For some
        if not mailToShow[pos]["id"] in mailsPerID:
            continue

        if not mailsPerID[ mailToShow[pos]["id"] ][ "children" ]:
            continue

        mailToShow[pos]["children"] = renderThread(
            mailsPerID=mailsPerID,
            thread_current_mail_id=mailsPerID[ mailToShow[pos]["id"] ][ "children" ][0],
            currently_selected_mail_id=currently_selected_mail_id,
            linkPrefix=linkPrefix,
        )

    mailToShow.sort(key=lambda val: val["date"])

    return renderTemplate("thread-ul.tpl", None, mailToShow=mailToShow, linkPrefix=linkPrefix)




attCount = 0
lastAttName = ""
att_count = 0
last_att_filename = ""


def getLogFile():
    return "%s/%s" % (maildir_raw, 'proccess.txt')


def getHeader(raw, header):
    header = header.lower() + ':'

    lines = raw.split("\n")
    for line in lines:
        if not line.lower().startswith(header):
            continue


        response = line.strip()[len(header):]
        if header in ('from:', 'to:'):
            response = email.utils.parseaddr(response)[1]

        return response


def renderIndexPage():
    global server

    now = datetime.datetime.now()

    allInfo = []
    allInfo.append({
        "title": "IMAP Server",
        "value": server.get('domain'),
    })

    allInfo.append({
        "title": "Username",
        "value": server.get('username'),
    })

    allInfo.append({
        "title": "Date of backup",
        "value": str(now),
    })

    renderPage(
        "%s/%s" % (maildir_result, "index.html"),
        headerTitle="Email Backup index page",
        linkPrefix=".",
        content=renderTemplate(
            "page-index.html.tpl",
            None,
            allInfo=allInfo,
            linkPrefix=".",
        )
    )


def printImapFolders(currentParent = '', intend = '  '):
    """
    Prints list of folders
    """

    if not currentParent:
        print("All folders")

    allFolders = getMailFolders()
    for folder_id in allFolders:
        folder = allFolders[folder_id]
        if folder["parent"] != currentParent:
            continue

        if allFolders[folder_id]["selected"]:
            print("%s**%s (%s)" % (intend, allFolders[folder_id]["title"], folder_id))
        else:
            print("%s%s (%s)" % (intend, allFolders[folder_id]["title"], folder_id))
        printImapFolders(folder_id, intend + "    ")


def returnWelcome():
    print("########################################################")
    print("# IMAP to Local HTML Backup by Charalampos Tsmipouris  #")
    print("########################################################")
    print("")
    print("Runtime Information:")
    print(sys.version)
    print("")


def extract_date(email):
    date = email.get('Date')
    return parsedate(date)


def getMailContent(mail):
    """
    Walks mail and returns mail content
    """
    content_of_mail_text = ""
    content_of_mail_html = ""
    attachments = []

    for part in mail.walk():
        part_content_maintype = part.get_content_maintype()
        part_content_type = part.get_content_type()
        part_charset = part.get_charsets()

        part_transfer_encoding = part.get_all("Content-Transfer-Encoding")
        if part_transfer_encoding:
            part_transfer_encoding = part_transfer_encoding[0]

        if part_content_type in ('text/plain', 'text/html'):
            part_decoded_contents = part.get_payload(decode=True)
            if part_transfer_encoding is None or part_transfer_encoding == "binary":
                part_transfer_encoding = part_charset[0]

            part_decoded_contents = normalize(part_decoded_contents, part_transfer_encoding)

            if part_content_type == 'text/plain':
                content_of_mail_text += part_decoded_contents
                continue

            if part_content_type == 'text/html':
                content_of_mail_html += part_decoded_contents
                continue

        # Attachment
        if not part.get('Content-Disposition') is None:
            if part.get_content_maintype() == 'multipart':
                continue

            attachment_content = part.get_payload(decode=True)
            # Empty file?
            if not attachment_content:
                continue

            attachment_filename_default = 'no-name-%d' % (len(attachments) + 1)

            if part.get_filename():
                attachment_filename = normalize(part.get_filename(), 'header')
            else:
                attachment_filename = attachment_filename_default

            filename_parts = attachment_filename.split(".")

            filename_ext = filename_parts[-1]
            filename_rest = filename_parts[:-1]
            filename_slug = "%s.%s" % (slugify_safe('.'.join(filename_rest), defaultVal=attachment_filename_default), filename_ext.lower())

            attachments.append({
                "title": attachment_filename,
                "slug": filename_slug,
                "filename": attachment_filename,
                "mimetype": part_content_type,
                "maintype": part_content_maintype,
                "content": attachment_content,
                "size": len(attachment_content),
            })

    if content_of_mail_text:
        content_of_mail_text = re.sub(r"(?i)<html>.*?<head>.*?</head>.*?<body>", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)</body>.*?</html>", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)<!DOCTYPE.*?>", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)POSITION: absolute;", "", content_of_mail_text, flags=re.DOTALL)
        content_of_mail_text = re.sub(r"(?i)TOP: .*?;", "", content_of_mail_text, flags=re.DOTALL)


    if content_of_mail_html:
        content_of_mail_html = re.sub(r"(?i)<html>.*?<head>.*?</head>.*?<body>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)<base .*?>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)</body>.*?</html>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)<!DOCTYPE.*?>", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)POSITION: absolute;", "", content_of_mail_html, flags=re.DOTALL)
        content_of_mail_html = re.sub(r"(?i)TOP: .*?;", "", content_of_mail_html, flags=re.DOTALL)

    return content_of_mail_text, content_of_mail_html, attachments


def backup_mails_to_html_from_local_maildir(folder, mailsPerID):
    """
    Creates HTML files and folder index from a mailbox folder
    """
    print("Processing folder: %s" % normalize(folder_id, "utf7"), end="")

    global maildir_raw

    mails = {}

    local_maildir_folder = folder.replace("/", ".")
    local_maildir = mailbox.Maildir(os.path.join(maildir_raw), factory=None, create=True)
    try:
        maildir_folder = local_maildir.get_folder(local_maildir_folder)
    except mailbox.NoSuchMailboxError as e:
        renderPage(
            "%s/%s" % (maildir_result, mailFolders[folder]["file"]),
            headerTitle="Folder %s" % mailFolders[folder]["title"],
            linkPrefix=".",
            selectedFolder=folder,
            content=renderTemplate(
                "page-mail-list.tpl",
                None,
                mails=mails,
                linkPrefix=".",
                selectedFolder=folder,
            )
        )

        print("..Done!")
        return

    print("(%d)" % len(maildir_folder), end="")
    sofar = 0
    for mail in maildir_folder:
        mail_id = mail.get('Message-Id')
        if mail_id in mails:
            continue

        mail_subject = normalize(mail.get('Subject'), 'header')

        if not mail_subject:
            mail_subject = "(No Subject)"

        mail_from = normalize(mail.get('From'), 'header')
        mail_to = normalize(mail.get('To'), 'header')
        mail_date = email.utils.parsedate(normalize(mail.get('Date'), 'header'))
        if not mail_date:
            mail_date = (2000, 1, 1, 12, 0, 00, 0, 1, -1)

        if mail_id:
            mail_id_hash = hashlib.md5(mail_id.encode()).hexdigest()
        else:
            temp = "%s %s %s %s" % (mail_subject, mail_date, mail_from, mail_to)
            mail_id = hashlib.md5(temp.encode()).hexdigest()
            mail_id_hash = mail_id

        mail_folder = str(time.strftime("%Y/%m/%d", mail_date))
        mail_raw = ""
        error_decoding = ""

        try:
            mail_raw = normalize(mail.as_bytes())
        except Exception as e:
            error_decoding += "~> Error in mail.as_bytes(): %s" % str(e)

        try:
            os.makedirs("%s/%s" % (maildir_result, mail_folder))
        except:
            pass

        fileName = "%s/%s.html" % (mail_folder, mail_id_hash)
        content_of_mail_text, content_of_mail_html, attachments = "", "", []

        try:
            content_of_mail_text, content_of_mail_html, attachments = getMailContent(mail)
        except Exception as e:
            error_decoding += "~> Error in getMailContent: %s" % str(e)

        data_uri_to_download = ''
        try:
            data_uri_to_download = "data:text/plain;base64,%s" % base64.b64encode(mail_raw.encode())
        except Exception as e:
            error_decoding += "~> Error in data_uri_to_download: %s" % str(e)

        content_default = "raw"
        if content_of_mail_text:
            content_default = "text"
        if content_of_mail_html:
            content_default = "html"

        attachment_count = 0
        for attachment in attachments:
            attachment_count += 1
            attachment["path"] = "%s/%s-%02d-%s" % (mail_folder, mail_id_hash, attachment_count, attachment["slug"])
            attachment["link"] = "%s/%s-%02d-%s" % (mail_folder, mail_id_hash, attachment_count, attachment["slug"])
            try:
                with open("%s/%s" % (maildir_result, attachment["path"]), 'wb') as att_file:
                    att_file.write(attachment["content"])
            except Exception as e:
                error_decoding += "~> Error writing attachment: %s" % str(e)
                print("Error writing attachment: " + str(e) + ".\n")

        mailReplyTo = None
        mailReplyToRaw = normalize(mail.get('In-Reply-To'), 'header')
        if mailReplyToRaw and mailReplyToRaw in mailsPerID:
            mailReplyTo = mailsPerID[mailReplyToRaw]

        mails[mail_id] = {
            "id": mail_id,
            "from": mail_from,
            "to": mail_to,
            "subject": mail_subject,
            "date": str(time.strftime("%Y-%m-%d %H:%m", mail_date)),
            "size": len(mail_raw),
            "file": fileName,
            "link": "/%s" % fileName,
            "replyTo": mailReplyTo,
            "content": {
                "html": content_of_mail_html,
                "text": content_of_mail_text,
                "raw": mail_raw,
                "default": content_default,
            },
            "download": {
                "filename": "%s.eml" % mail_id_hash,
                "content": data_uri_to_download,
            },
            "attachments": attachments,
            "error_decoding": error_decoding,
            "folders": mailsPerID[mail_id]["folders"],
        }

        thread_parent = None
        if mailsPerID.get(mail_id, {}).get("parent") or len(mailsPerID.get(mail_id, {}).get("children", [])) > 0:
            thread_parent = mail_id
            while mailsPerID.get(thread_parent, {}).get("parent"):
                thread_parent = mailsPerID.get(thread_parent, {}).get("parent")

        renderPage(
            "%s/%s" % (maildir_result, mails[mail_id]["file"]),
            title="%s | %s" % (mail_subject, mailFolders[folder]["title"]),
            headerTitle=mails[mail_id]["subject"],
            linkPrefix="../../..",
            selectedFolder=mailsPerID[mail_id]["folders"],
            content=renderTemplate(
                "page-mail.tpl",
                None,
                mail=mails[mail_id],
                linkPrefix="../../..",
                selectedFolder=mailsPerID[mail_id]["folders"],
                thread=renderThread(
                    mailsPerID=mailsPerID,
                    thread_current_mail_id=thread_parent,
                    currently_selected_mail_id=mail_id,
                    linkPrefix="../../..",
                ),
            )
        )

        # No need to keep it in memory
        del mails[mail_id]["content"]
        del mails[mail_id]["download"]
        mails[mail_id]["attachments"] = len(mails[mail_id]["attachments"])

        sofar += 1
        if sofar % 10 == 0:
            print(sofar, end="")
        else:
            print('.', end="")
        sys.stdout.flush()
    print("Done!")

    print("    > Creating index file..", end="")
    sys.stdout.flush()
    renderPage(
        "%s/%s" % (maildir_result, mailFolders[folder]["file"]),
        title="Folder %s (%d)" % (mailFolders[folder]["title"], len(mails)),
        headerTitle="Folder %s (%d)" % (mailFolders[folder]["title"], len(mails)),
        linkPrefix=".",
        selectedFolder=folder,
        content=renderTemplate(
            "page-mail-list.tpl",
            None,
            mails=mails,
            linkPrefix=".",
            selectedFolder=folder,
        )
    )

    print("Done!")

returnWelcome()

imap_password = server.get('password')
if not imap_password:
    imap_password = getpass.getpass()

mail = mailutils.connectToImapMailbox(server.get('domain'), server.get('username'), imap_password, server.get('ssl', True))
printImapFolders()

allFolders = getMailFolders()
for folder_id in allFolders:
    if not allFolders[folder_id]["selected"]:
        continue

    print(("Getting messages from server from folder: %s.") % normalize(folder_id, "utf7"))
    retries = 0
    if server.get('ssl', True):
        try:
            mailutils.get_message_to_local(folder_id, mail, maildir_raw)
        except imaplib.IMAP4_SSL.abort:
            if retries < 5:
                print(("SSL Connection Abort. Trying again (#%i).") % retries)
                retries += 1
                mail = mailutils.connectToImapMailbox(server.get('domain'), server.get('username'), imap_password, server.get('ssl', True))
                mailutils.get_message_to_local(folder_id, mail, maildir_raw)
            else:
                print("SSL Connection gave more than 5 errors. Not trying again")
    else:
        try:
            mailutils.get_message_to_local(folder_id, mail, maildir_raw)
        except imaplib.IMAP4.abort:
            if retries < 5:
                print(("Connection Abort. Trying again (#%i).") % retries)
                retries += 1
                mail = mailutils.connectToImapMailbox(server.get('domain'), server.get('username'), imap_password)
                mailutils.get_message_to_local(folder_id, mail, maildir_raw)
            else:
                print("Connection gave more than 5 errors. Not trying again")

    print(("Done with folder: %s.") % normalize(folder_id, "utf7"))

renderIndexPage()
removeDir("%s/inc" % maildir_result)
copyDir(inc_location, "%s/inc" % maildir_result)

# We go through all folders and create a unified struct
# This will help references between mails
mailsPerID = {}
print("Creating unified list..", end="")
sys.stdout.flush()
for folder_id in allFolders:
    if not allFolders[folder_id]["selected"]:
        continue

    local_maildir_folder = folder_id.replace("/", ".")
    local_maildir = mailbox.Maildir(os.path.join(maildir_raw), factory=None, create=True)
    try:
        maildir_folder = local_maildir.get_folder(local_maildir_folder)
    except mailbox.NoSuchMailboxError as e:
        continue

    for mail in maildir_folder:
        mail_id = mail.get('Message-Id')
        mail_subject = normalize(mail.get('Subject'), 'header')
        mail_from = normalize(mail.get('From'), 'header')
        mail_to = normalize(mail.get('To'), 'header')

        if not mail_subject:
            mail_subject = "(No Subject)"

        mail_date = email.utils.parsedate(normalize(mail.get('Date'), 'header'))
        if not mail_date:
            mail_date = (2000, 1, 1, 12, 0, 00, 0, 1, -1)

        if mail_id:
            mail_id_hash = hashlib.md5(mail_id.encode()).hexdigest()
        else:
            temp = "%s %s %s %s" % (mail_subject, mail_date, mail_from, mail_to)
            mail_id = hashlib.md5(temp.encode()).hexdigest()
            mail_id_hash = mail_id

        mail_folder = str(time.strftime("%Y/%m/%d", mail_date))
        fileName = "%s/%s.html" % (mail_folder, mail_id_hash)

        if not mail_id in mailsPerID:
            mailsPerID[mail_id] = {}

        mailsPerID[mail_id]["id"] = mail_id
        mailsPerID[mail_id]["date"] = mail_date
        mailsPerID[mail_id]["subject"] = mail_subject
        mailsPerID[mail_id]["file"] = fileName
        mailsPerID[mail_id]["link"] = "/%s" % fileName

        if not mailsPerID[mail_id].get("children"):
            mailsPerID[mail_id]["children"] = []

        if not mailsPerID[mail_id].get("folders"):
            mailsPerID[mail_id]["folders"] = []

        if not folder_id in mailsPerID[mail_id]["folders"]:
            mailsPerID[mail_id]["folders"].append(folder_id)

        if not mailsPerID[mail_id].get("parent"):
            mailsPerID[mail_id]["parent"] = normalize(mail.get('In-Reply-To'), 'header')

            if mailsPerID[mail_id]["parent"]:
                if not mailsPerID[mail_id]["parent"] in mailsPerID:
                    mailsPerID[ mailsPerID[mail_id]["parent"] ] = {
                        "parent": "",
                        "children": [],
                    }

                if not mail_id in mailsPerID[ mailsPerID[mail_id]["parent"] ][ "children" ]:
                    mailsPerID[ mailsPerID[mail_id]["parent"] ][ "children" ].append(mail_id)

    print(".", end="")
    sys.stdout.flush()
print("Done (%d) mails" % len(mailsPerID))

for folder_id in allFolders:
    if not allFolders[folder_id]["selected"]:
        continue

    backup_mails_to_html_from_local_maildir(folder_id, mailsPerID)
