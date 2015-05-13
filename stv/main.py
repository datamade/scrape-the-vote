#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from argparse import ArgumentParser
import os
import shutil
import fileinput
from documentcloud import DocumentCloud
from .config import DC_USER, DC_PW
import sqlite3
import hashlib


def dispatch():

    parser = ArgumentParser(description="")
    parser_subparsers = parser.add_subparsers()
    sub_init = parser_subparsers.add_parser('init')
    sub_scrape = parser_subparsers.add_parser('scrape')

    sub_init.add_argument(dest='scrapername', help='the name of the scraper to initialize')
    sub_init.set_defaults(func=init)

    sub_scrape.add_argument(dest='scrapername', help='the name of the scraper to run')
    sub_scrape.set_defaults(func=scrape)

    args = parser.parse_args()
    args.func(args)


def init(args) :
    # create documents table if it doesn't exist
    con = sqlite3.connect('documents.db')
    with con:
        cur = con.cursor()
        sql_str = 'CREATE TABLE IF NOT EXISTS Documents ('  \
                    'id INTEGER PRIMARY KEY,'               \
                    'election_id INTEGER,'                  \
                    'url TEXT,'                             \
                    'name TEXT,'                            \
                    'file_hash TEXT,'                       \
                    'hierarchy TEXT,'                       \
                    'timestamp_server TEXT,'                \
                    'timestamp_local TEXT'                  \
                    ');'

        cur.execute(sql_str)
        con.commit()

    # if args.scrapername:

    #     # create project on document cloud
    # else:
    #     print('Please specify a scraper name')

def scrape(args) :
    dc_project = 'ndi'  # default document cloud project
    img_dir = 'images/' # the local directory where images will be downloaded

    if not os.path.exists(img_dir):
        os.makedirs(img_dir)

    if args.scrapername:
        module = __import__('stv.%s' % args.scrapername, globals(), locals(), ['Scraper'])
        scraper = getattr(module, 'Scraper')()
        if scraper.dc_project:
            dc_project = scraper.dc_project
        client = DocumentCloud(DC_USER, DC_PW)
        project, created = client.projects.get_or_create_by_title(dc_project)
        images = scraper.crawl()

        for image in images:
            print("url: %s" %image[0])
            head, tail = os.path.split(image[0])
            if os.path.exists(img_dir+tail):
                print("%s already exists" %tail)
            else:
                if not image[2]: # no post data required
                    r = scraper.get(image[0], stream=True)
                else: # post data required
                    r = scraper.post(image[0], data=image[2], stream=True)

                hasher = hashlib.sha1()
                file_hash = ''
                metadata = image[1]
                timestamp_server = ''
                timestamp_local = ''
                if r.status_code == 200: #what to do for other status codes?
                    with open(img_dir+tail, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            hasher.update(chunk)
                            f.write(chunk)
                            f.flush()
                    file_hash = hasher.hexdigest()
                    timestamp_server = r.headers['last-modified'] if 'last-modified' in r.headers else ''
                    timestamp_local = r.headers['date'] if 'date' in r.headers else ''
                
                # adding image to Documents table
                con = sqlite3.connect('documents.db')

                with con:
                    cur = con.cursor()
                    insert_str = 'INSERT INTO Documents \
                                (election_id,url,name,file_hash,hierarchy,timestamp_server,timestamp_local) \
                                VALUES (?,?,?,?,?,?,?);'
                    q_update = 'SELECT * FROM Documents where url=? and file_hash!=? and file_hash!=""'
                    q_duplicate = 'SELECT * FROM Documents where url=? and file_hash=?'
                    cur.execute(q_update,(image[0],file_hash))
                    is_update = cur.fetchone()
                    cur.execute(q_duplicate,(image[0],file_hash))
                    is_duplicate = cur.fetchone()
                    cur.execute(insert_str,(metadata['election_id'],image[0],tail,file_hash,metadata['hierarchy'],timestamp_server,timestamp_local))
                    con.commit()

                    if not is_duplicate:
                        # do something here if image is an update of an image we've already seen

                        # uploading image to document cloud
                        obj = client.documents.upload(img_dir+tail, project=str(project.id), data=metadata.encode('ascii'))
                    
                    #delete image file here

    else:
        print('Please specify a scraper name')
