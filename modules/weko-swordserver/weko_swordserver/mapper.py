# -*- coding: utf-8 -*-
#
# Copyright (C) 2024 National Institute of Informatics.
#
# WEKO-SWORDServer is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Module of weko-swordserver."""

from invenio_oaiharvester.harvester import JsonMapper

from .errors import WekoSwordserverException


class WekoSwordMapper(JsonMapper):
    """WekoSwordMapper."""
    def __init__(self, json, itemtype, json_map):
        """Init."""
        self.json = json
        self.itemtype = itemtype
        self.itemtype_name = itemtype.item_type_name.name
        self.json_map = json_map

    def map(self):
        """Maping JSON-LD;self.json Metadata into item_type format."""
        if self.is_deleted():
            return {}

        res = {
            "pubdate": str(self.datestamp()),
            "publish_status": self.json.get("record").get("header").get("publish_status"),
            "path": [self.json.get("record").get("header").get("indextree")]
        }

        item_map = self._create_item_map()
        metadata = self._create_metadata(item_map)

        files_info = []
        for k, v in self.itemtype.schema.get("properties").items():
            if v.get("title") == "File":
                files_info.append({"key": k, "items": metadata.get(k)})
        files_info = {"files_info": files_info}

        res = {**res, **files_info, **metadata}
        return res


    # TODO: Refactor mapping logic
    def _create_metadata(self, item_map):
        """Create metadata.

        Args:
            item_map (dict): item_map

        Returns:
            dict: mapped metadata
        """
        metadata = {}

        # Create metadata for each item in json_map
        for k, v in self.json_map.items():
            json_value = self._get_json_metadata_value(v)
            if json_value is None:
                continue
            type_of_item_type_path = self._get_type_of_item_type_path(item_map[k])
            self._create_metadata_of_a_property(metadata, item_map[k], type_of_item_type_path, json_value)
        return metadata


    def _get_json_metadata_value(self, json_map_key):
        """Get json value.

        If the value got from self.json is in list, the result is list.
        If the value got from self.json is in multiple dimensions, the result
        is multi dimension list.

        Examples:

        1. If the value of json_map_key includes single [] like below, the
           result is one dimension list.

            "example_key_1": {
                "key_arr": [
                    {
                        "key_val": "value1"
                    },
                    {
                        "key_val": "value2"
                    }
                ],
            }

            _get_json_metadata_value("example_key_1") -> ["value1", "value2"]


        2. If the value of json_map_key includes double [] like below, the
           result is two dimension list.

            "example_key_2": {
                "key_arr1": [
                    {
                        "key_arr2": [
                            {
                                "key_val": "value1"
                            },
                            {
                                "key_val": "value2"
                            }
                        ]
                    },
                    {
                        "key_arr2": [
                            {
                                "key_val": "value3"
                            },
                            {
                                "key_val": "value4"
                            }
                        ]
                    }
                ]
            }

            _get_json_metadata_value("example_key_2")
                -> [["value1", "value2"], ["value3", "value4"]]


        Args:
            json_map_key (str): Path of ProcessedJson get from json_map

        Returns:
            any: Element of metadata
        """
        # define internal functions
        def _detect_dict(json_keys, dict_, _in_list):
            """Get json value from dict.

            Args:
                json_keys (list): List of keys in dict
                dict_ (dict): Dict which contains metadata

            Returns:
                any: Element of metadata
            """
            json_key = json_keys[0]
            value = dict_.get(json_key)

            # No json_key in dict: {"other_key": value}
            if value is None:
                raise WekoSwordserverException(
                    f"Invalid mapping: No value got from {json_key}"
                )
            # dict in dict: {"json_key": {}}
            elif isinstance(value, dict):
                if len(json_keys) == 1:
                    return value
                return _detect_dict(json_keys[1:], value, _in_list)
            # list in dict: {"json_key": []}
            elif isinstance(value, list):
                _in_list = True
                if len(json_keys) == 1:
                    return value
                return _detect_list(json_keys[1:], value, _in_list)
            # value in dict: {"json_key": value}
            else:
                if len(json_keys) == 1:
                    return value
                else:
                    raise WekoSwordserverException(
                        f"Invalid mapping: Got {value} from {json_key} but still need to get {json_keys[1:]}"
                    )

        def _detect_list(json_keys, list_, _in_list):
            """Get json value from list.

            Args:
                json_keys (list): List of keys in list_of_dict
                list_ (list): List of dict which contains metadata

            Returns:
                any: Element of metadata
            """
            if not _in_list:
                raise WekoSwordserverException(
                    "Invalid mapping: No value got from list"
                )

            list_result = []
            for value in list_:
                # dict in list: [{}, {}, ...]
                if isinstance(value, dict):
                    result = _detect_dict(json_keys, value, _in_list)
                    list_result.append(result)
                # list in list: [[], [], ...]
                elif isinstance(value, list):
                    raise WekoSwordserverException(
                        "Invalid mapping: List in list not supported"
                    )
                # value in list: [value, value, ...]
                else:
                    raise WekoSwordserverException(
                        f"Invalid mapping: Got value from list but still need to get {json_keys}"
                    )
            return list_result

        json_keys = json_map_key.split('.')
        json_key = json_keys[0]
        value = self.json['record']['metadata'].get(json_key)

        if value is None:
            return None
        # dict in dict: {"json_key": {}}
        elif isinstance(value, dict):
            if len(json_keys) == 1:
                return value
            return _detect_dict(json_keys[1:], value, False)
        # list in dict: {"json_key": []}
        elif isinstance(value, list):
            return _detect_list(json_keys[1:], value, True)
        # value in dict: {"json_key": value}
        else:
            if len(json_keys) == 1:
                return value
            else:
                raise WekoSwordserverException(
                    f"Invalid mapping: Got {value} from {json_key} but still need to get {json_keys[1:]}"
                )


    def _get_type_of_item_type_path(self, item_map_key):
        """Get type of item type path.

        Args:
            item_map_key (str): Path of item type get from item_map

        Returns:
            list: Type of item type path
        """
        item_map_keys = item_map_key.split('.')
        type_of_item_type_path = []
        current_schema = self.itemtype.schema.get("properties")

        for item_map_key in item_map_keys:
            # item_map_key is not defined in item_tyep_schema
            if item_map_key not in current_schema:
                raise WekoSwordserverException(
                    f"Invalid mapping: {item_map_key} is not defined in item type schema"
                )
            # If "type" is "object" in item_tyep_schema, next path is in "properties"
            elif current_schema[item_map_key].get("type") == "object":
                type_of_item_type_path.append("object")
                current_schema = current_schema[item_map_key].get("properties")
            # If "type" is "array" in item_tyep_schema, next path is in "items" > "properties"
            elif current_schema[item_map_key].get("type") == "array":
                type_of_item_type_path.append("array")
                current_schema = current_schema[item_map_key].get("items").get("properties")
            # If "type" is other than "object" or "array" in item_tyep_schema, it is the end of the path
            else:
                type_of_item_type_path.append("value")

        # Validate length of type_of_item_type_path
        if len(type_of_item_type_path) != len(item_map_keys):
            raise WekoSwordserverException(
                f"Invalid mapping: type_of_item_type_path length: {len(type_of_item_type_path)} is not equal to item_map_keys length: {len(item_map_keys)}"
            )
        # Validate last element of type_of_item_type_path
        if type_of_item_type_path[-1] != "value":
            raise WekoSwordserverException(
                f"Invalid mapping: Last element of type_of_item_type_path must be value"
            )
        return type_of_item_type_path


    def _create_metadata_of_a_property(self, metadata, item_map_key, type_of_item_type_path, json_value):
        """Create metadata of a property.

        Args:
            metadata (dict): Metadata
            item_map_key (str): Path of item type get from item_map
            type_of_item_type_path (list): "type" of each key in ItemType, contains "value", "object", and "array"
            json_value (any): Value got from ProcessedJson
        """
        item_map_keys = item_map_key.split('.')
        dim_json_value = self._get_dimensions(json_value)
        num_array_type = type_of_item_type_path.count("array")

        # Check if json_value is too many dimensions
        if dim_json_value > num_array_type:
            # If json_value is list and dim_json_value - num_array_type == 1, use only first element
            if dim_json_value - num_array_type == 1:
                json_value = json_value[0]
                dim_json_value = self._get_dimensions(json_value)
            # If json_value is list and dim_json_value - num_array_type > 1, raise error
            else:
                raise WekoSwordserverException(
                    f"Invalid mapping: {json_value} contains too many dimensions"
                )

        # If num_array_type is bigger than  dim_json_value, only one {} created in array
        # then, dicrease diff_array and do the same thing until diff_array is 0
        diff_array = num_array_type - dim_json_value

        # If item_map_keys length is 1, it means that the item_map_keys contains only last key
        if len(item_map_keys) == 1:
            # If json_value is list, use only first element
            if dim_json_value > 0:
                metadata[item_map_keys[0]] = json_value[0]
            # If json_value is not list, use json_value
            else:
                metadata[item_map_keys[0]] = json_value
        # If item_map_keys length is more than 1, it is necessary to create nested metadata
        else:
            _item_map_key = item_map_keys[0]
            _type = type_of_item_type_path[0]

            # If _type is "value", _type must be the last element of type_of_item_type_path but still have more elements
            # because the length of type_of_item_type_path is equal to the length of item_map_keys
            if _type == "value":
                raise WekoSwordserverException(
                    f"Invalid mapping: 'value' must be the last key of type_of_item_type_path but got at first"
                )
            # If _type is "object", create nested metadata
            elif _type == "object":
                if not metadata.get(_item_map_key):
                    metadata[_item_map_key] = {}
                metadata = metadata[_item_map_key]
                self._create_child_metadata_of_a_property(diff_array, metadata, item_map_keys[1:], type_of_item_type_path[1:], json_value)
            # If _type is "array", do the following method
            elif _type == "array":
                # If diff_array is bigger than 0, create [{}] in metadata
                if diff_array > 0:
                    if not metadata.get(_item_map_key):
                        metadata[_item_map_key] = [{}]
                    metadata = metadata[_item_map_key][0]
                    diff_array -= 1
                    self._create_child_metadata_of_a_property(diff_array, metadata, item_map_keys[1:], type_of_item_type_path[1:], json_value)
                # If diff_array is 0, create [{}, {}, ...] in metadata
                # The number of {} is equal to the length of json_value
                else:
                    # If json_value is not list, raise error
                    if dim_json_value == 0:
                        raise WekoSwordserverException(
                            f"Invalid mapping: If diff_array is 0 and dim_json_value is 0, num_array_type must be 0 but got 1"
                        )
                    # If json_value is list, create nested metadata for each element of json_value
                    else:
                        if not metadata.get(_item_map_key):
                            metadata[_item_map_key] = [{} for _ in range(len(json_value))]
                        metadata = metadata[_item_map_key]

                        # Create nested metadata for each element of json_value
                        for i in range(len(json_value)):
                            self._create_child_metadata_of_a_property(diff_array, metadata[i], item_map_keys[1:], type_of_item_type_path[1:], json_value[i])
        return


    def _create_child_metadata_of_a_property(self, diff_array, child_metadata, item_map_keys, type_of_item_type_path, json_value):
        """Create child metadata of a property.

        Args:
            diff_array (int): The number of "array" in type_of_item_type_path - the number of dimensions of json_value
            child_metadata (dict): Child metadata
            item_map_keys (list): List of keys in ItemType
            type_of_item_type_path (list): "type" of each key in ItemType, contains "value", "object", and "array"
            json_value (any): Value got from ProcessedJson
        """
        dim_json_value = self._get_dimensions(json_value)

        # If item_map_keys length is 1, it means that the item_map_keys contains only last key
        if len(item_map_keys) == 1:
            # Only if json_value is not None, add json_value to metadata
            if json_value is not None:
                child_metadata[item_map_keys[0]] = json_value
        # If item_map_keys length is more than 1, it is necessary to create nested metadata
        else:
            _item_map_key = item_map_keys[0]
            _type = type_of_item_type_path[0]

            # If _type is "value", add json_value to metadata
            if _type == "value":
                # Only if json_value is not None, add json_value to metadata
                if json_value is not None:
                    child_metadata[_item_map_key] = json_value
            # If _type is "object", create nested metadata
            elif _type == "object":
                if not child_metadata.get(_item_map_key):
                    child_metadata[_item_map_key] = {}
                child_metadata = child_metadata[_item_map_key]
                self._create_child_metadata_of_a_property(diff_array, child_metadata, item_map_keys[1:], type_of_item_type_path[1:], json_value)
            # If _type is "array", do the following method
            elif _type == "array":
                # If diff_array is bigger than 0, create [{}] in metadata
                if diff_array > 0:
                    if not child_metadata.get(_item_map_key):
                        child_metadata[_item_map_key] = [{}]
                    child_metadata = child_metadata[_item_map_key][0]
                    diff_array -= 1
                    self._create_child_metadata_of_a_property(diff_array, child_metadata, item_map_keys[1:], type_of_item_type_path[1:], json_value)
                # If diff_array is 0, create [{}, {}, ...] in metadata
                # The number of {} is equal to the length of json_value
                else:
                    # If json_value is not list, raise error
                    if dim_json_value == 0:
                        raise WekoSwordserverException(
                            f"Invalid mapping: If diff_array is 0 and dim_json_value is 0, num_array_type must be 0 but got 1"
                        )
                    # If json_value is list, create nested metadata for each element of json_value
                    else:
                        if not child_metadata.get(_item_map_key):
                            child_metadata[_item_map_key] = [{} for _ in range(len(json_value))]
                        child_metadata = child_metadata[_item_map_key]

                        # Create nested metadata for each element of json_value
                        for i in range(len(json_value)):
                            self._create_child_metadata_of_a_property(diff_array, child_metadata[i], item_map_keys[1:], type_of_item_type_path[1:], json_value[i])
        return


    def _get_dimensions(self, lst):
        """
        Get dimensions of list.

        e.g.
            1 -> 0
            [1, 2, 3] -> 1
            [[1, 2], [3, 4]] -> 2
            [[[1, 2], [3, 4]], [[5, 6], [7, 8]]] -> 3
            [] -> 1
        """
        # If lst is not list, return 0
        if not isinstance(lst, list):
            return 0
        # If lst is empty, return 1
        elif not lst:
            return 1
        # If lst is not empty, return 1 + dimensions of lst[0]
        else:
            return 1 + self._get_dimensions(lst[0])


    def is_valid_mapping(self):
        """Check if the mapping is valid."""
        try:
            self.validate_mapping()
        except WekoSwordserverException:
            return False
        return True


    def validate_mapping(self):
        """Validate mapping."""
        item_map = self._create_item_map()
        # FIXME: if required metadata is not defined in the json file.
        # not only top level but also child metadata should be checked.
        error_msg = []
        for k, v in self.json_map.items():
            if k not in item_map:
                error_msg.append(f"{k} is not defined.")

        if error_msg:
            raise WekoSwordserverException(error_msg)