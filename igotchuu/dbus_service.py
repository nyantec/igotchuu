# Copyright © 2022 nyantec GmbH <oss@nyantec.com>
# Written by Vika Shleina <vsh@nyantec.com>
#
# Provided that these terms and disclaimer and all copyright notices
# are retained or reproduced in an accompanying document, permission
# is granted to deal in this work without restriction, including un‐
# limited rights to use, publicly perform, distribute, sell, modify,
# merge, give away, or sublicence.
#
# This work is provided "AS IS" and WITHOUT WARRANTY of any kind, to
# the utmost extent permitted by applicable law, neither express nor
# implied; without malicious intent or gross negligence. In no event
# may a licensor, author or contributor be held liable for indirect,
# direct, other damage, loss, or other issues arising in any way out
# of dealing in the work, even if advised of the possibility of such
# damage or existence of a defect, except proven that it results out
# of said person's immediate fault when using the work as intended.
from gi.repository import Gio, GLib, GObject

def _build_variant(name, py_value):
    s_data = GLib.VariantDict.new()
    for key, value in py_value.items():
        gvalue = GLib.Variant('ay', value)
        s_data.insert_value(key, gvalue)
    return s_data.end()


class DbusService:
    def __init__(self, dbus, introspection_xml, publish_path):
        self.node_info = Gio.DBusNodeInfo.new_for_xml(introspection_xml).interfaces[0]
        method_outargs = {}
        method_inargs = {}
        property_sig = {}
        for method in self.node_info.methods:
            method_outargs[method.name] = '(' + ''.join([arg.signature for arg in method.out_args]) + ')'
            method_inargs[method.name] = tuple(arg.signature for arg in method.in_args)
        self.method_inargs = method_inargs
        self.method_outargs = method_outargs
        self.con = dbus
        self.registration_id = self.con.register_object(
            publish_path,
            self.node_info,
            self.handle_method_call,
            self.prop_getter,
            self.prop_setter
        )

    def handle_method_call(
            self,
            connection: Gio.DBusConnection,
            sender: str,
            object_path: str,
            interface_name: str,
            method_name: str,
            params: GLib.Variant,
            invocation: Gio.DBusMethodInvocation
    ):
        """
        This is the top-level function that handles method calls to
        the server.
        """
        args = list(params.unpack())
        for i, sig in enumerate(self.method_inargs[method_name]):
            # Check if there is a Unix file descriptor in the signature
            if sig == 'h':
                msg = invocation.get_message()
                fd_list = msg.get_unix_fd_list()
                args[i] = fd_list.get(args[i])
        # Get the method from the Python class
        func = self.__getattribute__(method_name)
        result = func(*args)
        if result is None:
            result = ()
        else:
            result = (result,)
        outargs = ''.join([_.signature
                           for _ in invocation.get_method_info().out_args])
        send_result = GLib.Variant(f'({outargs})', result)
        invocation.return_value(send_result)

    def prop_getter(self,
                    connection: Gio.DBusConnection,
                    sender: str,
                    object: str,
                    iface: str,
                    name: str):
        """Method for moving properties from Python Class to D-Bus"""
        py_value = self.__getattribute__(name)
        signature = self.node_info.lookup_property(name).signature
        if 'v' in signature:
            dbus_value = _build_variant(name, py_value)
            return dbus_value
        if py_value:
            return GLib.Variant(signature, py_value)
        return None

    def prop_setter(self,
                    connection: Gio.DBusConnection,
                    sender: str,
                    object: str,
                    iface: str,
                    name: str,
                    value: GLib.Variant):
        """Method for moving properties between D-Bus and Python Class"""
        self.__setattr__(name, value.unpack())
        return True

    def unregister(self):
        return self.con.unregister_object(self.registration_id)
