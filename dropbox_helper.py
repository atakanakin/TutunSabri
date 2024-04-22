'''
Special thanks to the author of this code: Jae Won Choi
Github: https://github.com/jwc-rad 
Medium: https://jwc-rad.medium.com/
'''
import dropbox
import os
import time

class DropBoxUpload:
    def __init__(self,token,timeout=900,chunk=8):
        self.token = token
        self.timeout = timeout
        self.chunk = chunk
 
    def UpLoadFile(self,upload_path,file_path):
        dbx = dropbox.Dropbox(self.token,timeout=self.timeout)
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
        link = self.create_shared_link(dest_path)
        return link
                
    def create_shared_link(self, path):
        dbx = dropbox.Dropbox(self.token,timeout=self.timeout)
        shared_link = dbx.sharing_create_shared_link(path)
        return shared_link.url