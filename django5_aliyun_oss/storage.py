# oss_storage/storage.py
import os
from datetime import datetime
from urllib.parse import urljoin

import oss2
from django.conf import settings
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

@deconstructible
class AliyunOSSStorage(Storage):
    """
    Aliyun OSS Storage Backend for Django
    
    Usage:
        ALIYUN_OSS = {
            'ACCESS_KEY_ID': 'your-access-key-id',
            'ACCESS_KEY_SECRET': 'your-access-key-secret',
            'ENDPOINT': 'your-endpoint',
            'BUCKET_NAME': 'your-bucket-name',
            'URL_EXPIRE_SECONDS': 3600,  # 签名URL的过期时间
        }
    """
    
    def __init__(self):
        self.access_key_id = settings.ALIYUN_OSS.get('ACCESS_KEY_ID')
        self.access_key_secret = settings.ALIYUN_OSS.get('ACCESS_KEY_SECRET')
        self.endpoint = settings.ALIYUN_OSS.get('ENDPOINT')
        self.bucket_name = settings.ALIYUN_OSS.get('BUCKET_NAME')
        self.url_expire_seconds = settings.ALIYUN_OSS.get('URL_EXPIRE_SECONDS', 3600)
        
        # 创建 Auth 实例
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        # 创建 Bucket 实例
        self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)

    def _get_key(self, name):
        """
        清理文件路径，确保格式正确
        """
        return os.path.normpath(name).replace('\\', '/')

    def _open(self, name, mode='rb'):
        """
        获取文件对象
        """
        key = self._get_key(name)
        return self.bucket.get_object(key)

    def _save(self, name, content):
        """
        保存文件到 OSS
        """
        key = self._get_key(name)
        
        # 如果文件对象有 chunks 方法(例如 UploadedFile)，使用 chunks 上传
        if hasattr(content, 'chunks'):
            self.bucket.put_object(key, content.chunks())
        else:
            self.bucket.put_object(key, content.read())
            
        return name

    def exists(self, name):
        """
        判断文件是否存在
        """
        try:
            self.bucket.get_object_meta(self._get_key(name))
            return True
        except oss2.exceptions.NoSuchKey:
            return False

    def url(self, name):
        """
        生成文件的访问 URL
        """
        key = self._get_key(name)
        # 生成带签名的 URL
        return self.bucket.sign_url('GET', key, self.url_expire_seconds)

    def size(self, name):
        """
        获取文件大小
        """
        key = self._get_key(name)
        return self.bucket.get_object_meta(key).content_length

    def delete(self, name):
        """
        删除文件
        """
        key = self._get_key(name)
        self.bucket.delete_object(key)

    def get_modified_time(self, name):
        """
        获取文件最后修改时间
        """
        key = self._get_key(name)
        return datetime.fromtimestamp(self.bucket.get_object_meta(key).last_modified)

    def get_valid_name(self, name):
        """
        返回有效的文件名
        """
        return name

    def get_available_name(self, name, max_length=None):
        """
        返回可用的文件名
        """
        if self.exists(name):
            dir_name, file_name = os.path.split(name)
            file_root, file_ext = os.path.splitext(file_name)
            count = 1
            
            while self.exists(name):
                # file.txt -> file_1.txt
                name = os.path.join(dir_name, f"{file_root}_{count}{file_ext}")
                count += 1
                
        return name

    def listdir(self, path):
        """
        列出目录下的文件和子目录
        """
        path = self._get_key(path)
        if path and not path.endswith('/'):
            path += '/'

        directories = set()
        files = []

        for obj in oss2.ObjectIterator(self.bucket, prefix=path):
            relative_path = obj.key[len(path):] if path != '/' else obj.key
            if not relative_path:
                continue

            # 如果包含 /，说明是子目录
            if '/' in relative_path:
                directories.add(relative_path.split('/')[0])
            else:
                files.append(relative_path)

        return list(directories), files