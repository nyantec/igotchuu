def to_glib_variant_dict(d):
    """A helper function to translate a dict (usually from JSON) to `GLib.Variant`.

    This function cuts corners: it only handles `int`, `float`, `str` and `list`
    of `str`, throwing `TypeError` otherwise.

    It could be extended by encoding lists using variants and special-casing
    lists where all elements are of the same type, but this is left as an
    exercise to the reader.

    """
    glib_dict = GLib.VariantBuilder.new(GLib.VariantType.new("a{sv}"))
    for key, val in d.items():
        if type(val) == int:
            glib_progress.add_value(
                GLib.Variant.new_dict_entry(
                    GLib.Variant.new_string(key),
                    GLib.Variant.new_variant(
                        GLib.Variant.new_int64(val)
                    )
                )
            )
        elif type(val) == float:
            glib_progress.add_value(
                GLib.Variant.new_dict_entry(
                    GLib.Variant.new_string(key),
                    GLib.Variant.new_variant(
                        GLib.Variant.new_double(val)
                    )
                )
            )
        elif type(val) == str:
            glib_progress.add_value(
                GLib.Variant.new_dict_entry(
                GLib.Variant.new_string(key),
                    GLib.Variant.new_variant(
                        GLib.Variant.new_string(val)
                    )
                )
            )
        elif type(val) == list and all(map(lambda i: type(i) == str, val)):
            glib_progress.add_value(
                GLib.Variant.new_dict_entry(
                    GLib.Variant.new_string(key),
                    GLib.Variant.new_variant(
                        GLib.Variant.new_array(
                            GLib.VariantType.new("s"),
                            list(map(GLib.Variant.new_string, val))
                        )
                    )
                )
            )
        else:
            raise TypeError("Cannot handle key {} with type {}".format(key, type(val)))

    return glib_dict.end()
