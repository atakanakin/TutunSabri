'''
***DEPRECATED***
Special thanks to the author of this code: Jae Won Choi
Github: https://github.com/jwc-rad 
Medium: https://jwc-rad.medium.com/
Also, thanks to the https://stackoverflow.com/questions/70641660/how-do-you-get-and-use-a-refresh-token-for-the-dropbox-api-python-3-x
This code is a modified version of the code provided by the author.
Simply follow the instructions provided in the link above to get the oauth2_refresh_token.
'''
import dropbox
import os
import time
import requests
import datetime

class DropBoxUpload:
    def __init__(self,app_key, app_secret, oauth2_refresh_token, timeout=900, chunk=64):
        self.app_key = app_key
        self.app_secret = app_secret
        self.oauth2_refresh_token = oauth2_refresh_token
        self.timeout = timeout
        self.chunk = chunk
    
    def get_access_token(self):
        url = "https://api.dropbox.com/oauth2/token"
        data = {
            "refresh_token": self.oauth2_refresh_token,
            "grant_type": "refresh_token",
            "client_id": self.app_key,
            "client_secret": self.app_secret
        }

        response = requests.post(url, data=data)

        # The response will be in JSON format, you can convert it to a Python dictionary using .json()
        response_dict = response.json()
        access_token = response_dict['access_token']
        return access_token
 
    def UpLoadFile(self,upload_path,file_path):
        acces_token = self.get_access_token()        
        dbx = dropbox.Dropbox(acces_token,timeout=self.timeout)
        
        # check if there are any files older than 1 day and delete them
        metadata = dbx.files_list_folder(upload_path)
        current_time = datetime.datetime.now()
        for file in metadata.entries:
            time_modified = file.client_modified
            if (current_time - time_modified).days > 1:
                dbx.files_delete_v2(file.path_lower)
                print('Deleted: ', file.path_display)
                
        # upload the file        
        file_size = os.path.getsize(file_path)
        CHUNK_SIZE = self.chunk * 1024 * 1024
        dest_path = upload_path + '/' + os.path.basename(file_path)
        since = time.time()
        with open(file_path, 'rb') as f:
            uploaded_size = 0
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), dest_path)
                time_elapsed = time.time() - since
                print('Uploaded {:.2f}%'.format(100).ljust(15) + ' --- {:.0f}m {:.0f}s'.format(time_elapsed//60,time_elapsed%60).rjust(15))
            else:
                upload_session_start_result = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id,
                                                           offset=f.tell())
                commit = dropbox.files.CommitInfo(path=dest_path)
                while f.tell() <= file_size:
                    if ((file_size - f.tell()) <= CHUNK_SIZE):
                        dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                        time_elapsed = time.time() - since
                        print('Uploaded {:.2f}%'.format(100).ljust(15) + ' --- {:.0f}m {:.0f}s'.format(time_elapsed//60,time_elapsed%60).rjust(15))
                        break
                    else:
                        dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE),cursor)
                        cursor.offset = f.tell()
                        uploaded_size += CHUNK_SIZE
                        uploaded_percent = 100*uploaded_size/file_size
                        time_elapsed = time.time() - since
                        print('Uploaded {:.2f}%'.format(uploaded_percent).ljust(15) + ' --- {:.0f}m {:.0f}s'.format(time_elapsed//60,time_elapsed%60).rjust(15), end='\r')
        
        # create a shared link
        link = dbx.sharing_create_shared_link(dest_path)
        return link.url
    