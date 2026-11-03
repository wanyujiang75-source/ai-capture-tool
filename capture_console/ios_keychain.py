"""Restricted macOS Keychain access for this tool's own iPhone pairing only."""

import ctypes as c
import sys


class IOSPairingError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class MacOSPairingKeychain:
    def __init__(self, account, *, service='com.local.capture.ios.pairing.v1'):
        self.account = account
        self.service = service

    def _operation(self, action, data=None):
        if sys.platform != 'darwin':
            raise IOSPairingError('ios_pairing_storage', 'iPhone身份复用目前仅支持macOS钥匙串。')
        cf = c.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        sec = c.CDLL('/System/Library/Frameworks/Security.framework/Security')
        cf.CFStringCreateWithCString.argtypes = [c.c_void_p, c.c_char_p, c.c_uint32]
        cf.CFStringCreateWithCString.restype = c.c_void_p
        cf.CFDataCreate.argtypes = [c.c_void_p, c.c_void_p, c.c_long]
        cf.CFDataCreate.restype = c.c_void_p
        cf.CFDictionaryCreateMutable.argtypes = [c.c_void_p, c.c_long, c.c_void_p, c.c_void_p]
        cf.CFDictionaryCreateMutable.restype = c.c_void_p
        cf.CFDictionarySetValue.argtypes = [c.c_void_p, c.c_void_p, c.c_void_p]
        cf.CFRelease.argtypes = [c.c_void_p]
        cf.CFDataGetLength.argtypes = [c.c_void_p]
        cf.CFDataGetLength.restype = c.c_long
        cf.CFDataGetBytePtr.argtypes = [c.c_void_p]
        cf.CFDataGetBytePtr.restype = c.c_void_p
        sec.SecItemCopyMatching.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
        sec.SecItemAdd.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
        sec.SecItemDelete.argtypes = [c.c_void_p]
        for name in ('SecItemCopyMatching', 'SecItemAdd', 'SecItemDelete'):
            getattr(sec, name).restype = c.c_int32

        def constant(name, library=sec):
            return c.c_void_p.in_dll(library, name).value

        query = cf.CFDictionaryCreateMutable(None, 0, None, None)
        owned = [query]
        result = c.c_void_p()
        try:
            def set_constant(key, value):
                cf.CFDictionarySetValue(query, constant(key), constant(value))

            def set_string(key, value):
                reference = cf.CFStringCreateWithCString(None, value.encode(), 0x08000100)
                owned.append(reference)
                cf.CFDictionarySetValue(query, constant(key), reference)

            set_constant('kSecClass', 'kSecClassGenericPassword')
            set_string('kSecAttrService', self.service)
            set_string('kSecAttrAccount', self.account)
            # Never prompt for or read another application's credentials.
            set_constant('kSecUseAuthenticationUI', 'kSecUseAuthenticationUIFail')
            if action == 'read':
                cf.CFDictionarySetValue(query, constant('kSecReturnData'), constant('kCFBooleanTrue', cf))
                set_constant('kSecMatchLimit', 'kSecMatchLimitOne')
                status = sec.SecItemCopyMatching(query, c.byref(result))
            elif action == 'create':
                reference = cf.CFDataCreate(None, data, len(data))
                owned.append(reference)
                cf.CFDictionarySetValue(query, constant('kSecValueData'), reference)
                set_string('kSecAttrLabel', 'Capture Tool iPhone Pairing')
                status = sec.SecItemAdd(query, None)
            elif action == 'delete':
                status = sec.SecItemDelete(query)
            else:
                raise ValueError('unknown Keychain operation')
            if status == -25300 and action in ('read', 'delete'):
                return None
            if status != 0:
                raise IOSPairingError('ios_pairing_storage', '无法访问本工具钥匙串身份；请解锁Mac后重试，不会更换证书或明文保存密钥。')
            if result.value:
                length = cf.CFDataGetLength(result)
                if not 0 < length <= 32768:
                    raise IOSPairingError('ios_pairing_invalid', '抓包身份异常，请恢复手机网络并结束连接后重新配置。')
                return c.string_at(cf.CFDataGetBytePtr(result), length)
            return None
        finally:
            if result.value:
                cf.CFRelease(result)
            for reference in reversed(owned):
                cf.CFRelease(reference)

    def read(self):
        return self._operation('read')

    def create(self, data):
        if not 0 < len(data) <= 32768:
            raise ValueError('invalid pairing size')
        self._operation('create', data)

    def delete(self):
        self._operation('delete')
