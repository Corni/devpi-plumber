import os
from contextlib import contextmanager
from unittest import TestCase

import requests
from devpi_plumber.client import DevpiClientError, volatile_index
from devpi_plumber.server import TestServer


@contextmanager
def cd(path):
    old_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)


class ClientTest(TestCase):
    """
    Assert that the plumber devpi client behaves as expected.
    """

    def test_login_success(self):
        users = {"user": {"password": "secret"}}

        with TestServer(users) as devpi:
            self.assertIn("credentials valid", devpi.login("user", "secret"))
            self.assertEquals("user", devpi.user)

    def test_login_error(self):
        users = {"user": {"password": "secret"}}

        with TestServer(users) as devpi:
            with self.assertRaisesRegexp(DevpiClientError, "401 Unauthorized"):
                devpi.login('user', 'wrong password')
            self.assertEquals('root', devpi.user)

    def test_logoff(self):
        with TestServer() as devpi:
            self.assertIn("login information deleted", devpi.logoff())
            self.assertIsNone(devpi.user)

    def test_use(self):
        with TestServer() as devpi:
            expected = "current devpi index: " + devpi.url + "/root/pypi"
            self.assertIn(expected, devpi.use("root/pypi"))

    def test_url(self):
        with TestServer() as devpi:
            devpi.use("root/pypi")
            self.assertEquals(devpi.server_url + "/root/pypi", devpi.url)

    def test_create_user(self):
        with TestServer() as devpi:
            devpi.create_user("user", password="password", email="user@example.com")
            self.assertEqual(200, requests.get(devpi.server_url + "/user").status_code)

    def test_modify_user(self):
        users = {"user": {"password": "secret"}}

        with TestServer(users) as devpi:
            devpi.modify_user("user", password="new secret")
            self.assertIn("credentials valid", devpi.login("user", "new secret"))

    def test_create_index(self):
        users = {"user": {"password": "secret"}}

        with TestServer(users) as devpi:
            devpi.create_index("user/index")
            self.assertEqual(200, requests.get(devpi.server_url + "/user/index").status_code)

    def test_modify_index(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {"bases": ""}}

        with TestServer(users, indices) as devpi:
            self.assertIn("changing bases", devpi.modify_index("user/index", bases="root/pypi"))

    def test_list_indices(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            listed = devpi.list_indices()
            self.assertEquals(2, len(listed))
            self.assertIn('root/pypi', listed)
            self.assertIn('user/index', listed)

    def test_list_indices_by_user(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}, "user/index2": {}}

        with TestServer(users, indices) as devpi:
            listed = devpi.list_indices(user='root')
            self.assertListEqual(['root/pypi'], listed)

            listed = devpi.list_indices(user='user')
            self.assertSetEqual(set(['user/index', 'user/index2']), set(listed))

    def test_upload_file(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            devpi.upload("tests/fixture/package/dist/test-package-0.1.tar.gz")

            self.assertEqual(200, requests.get(devpi.server_url + "/user/index/+simple/test_package").status_code)

    def test_upload_folder(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            devpi.upload("tests/fixture/package/", directory=True)

            self.assertEqual(200, requests.get(devpi.server_url + "/user/index/+simple/test_package").status_code)

    def test_upload_dry_run(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            devpi.upload("tests/fixture/package/dist/test-package-0.1.tar.gz", dry_run=True)

            self.assertIn('Not Found', requests.get(devpi.server_url + "/user/index/+simple/test_package").text)

    def test_upload_with_docs(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            with cd('tests/fixture/package'):
                devpi.upload(with_docs=True)

    def test_list_existing_package(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            devpi.upload("tests/fixture/package/", directory=True)

            expected = ['test_package-0.1-cp34-cp34m-linux_x86_64.whl', 'test-package-0.1.tar.gz']
            actual = devpi.list("test_package==0.1")

            self.assertEqual(len(actual), len(expected))
            for entry in actual:
                self.assertTrue(any(entry.endswith(package) for package in expected))

    def test_list_nonexisting_package(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.use("user/index")

            self.assertEqual([], devpi.list("test_package==0.1"))

    def test_list_error(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            with self.assertRaisesRegexp(DevpiClientError, "not connected to an index"):
                devpi.list("test_package==0.1")

    def test_replica(self):
        with TestServer(config={'port': 2414}) as devpi:
            with TestServer(config={'master-url': devpi.server_url, 'port': 2413}) as replica:

                self.assertNotEqual(devpi.server_url, replica.server_url)

    def test_remove(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            devpi.upload("tests/fixture/package/", directory=True)

            devpi.remove("test_package==0.1")

            self.assertListEqual([], devpi.list("test_package==0.1"))

    def test_remove_invalid(self):
        users = {"user": {"password": "secret"}}
        indices = {"user/index": {}}

        with TestServer(users, indices) as devpi:
            devpi.login("user", "secret")
            devpi.use("user/index")
            devpi.upload("tests/fixture/package/", directory=True)

            devpi.remove("test_package==0.2")

            self.assertEquals(2, len(devpi.list("test_package==0.1")))


class VolatileIndexTests(TestCase):

    def test_set_unset_volatile_flag(self):
        index = "user/index"
        users = {"user": {"password": "secret"}}
        indices = {index: {'volatile': False}}

        with TestServer(users, indices) as client:
            client.login("user", "secret")

            with volatile_index(client, index):
                self.assertIn('volatile=True', client.modify_index(index))
            self.assertIn('volatile=False', client.modify_index(index))

            with self.assertRaises(Exception):
                with volatile_index(client, 'user/index'):
                    raise Exception("Woops")
            self.assertIn('volatile=False', client.modify_index(index))

    def test_throw_when_not_forced(self):
        index = "user/index"
        users = {"user": {"password": "secret"}}
        indices = {index: {'volatile': False}}

        with TestServer(users, indices) as client:
            client.login("user", "secret")

            with self.assertRaises(Exception):
                with volatile_index(client, 'user/index', force_volatile=False):
                    pass
            self.assertIn('volatile=False', client.modify_index(index))
