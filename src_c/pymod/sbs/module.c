#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include "hat/sbs.h"


typedef struct {
    PyObject *common_Ref;
    PyObject *common_BooleanType;
    PyObject *common_IntegerType;
    PyObject *common_FloatType;
    PyObject *common_StringType;
    PyObject *common_BytesType;
    PyObject *common_ArrayType;
    PyObject *common_TupleType;
    PyObject *common_UnionType;
} module_state_t;


static ssize_t encode_generic(hat_buff_t *buff, module_state_t *module_state,
                              PyObject *refs, PyObject *t, PyObject *value);
static PyObject *decode_generic(hat_buff_t *buff, module_state_t *module_state,
                                PyObject *refs, PyObject *t);


static inline bool is_type(PyObject *inst, PyObject *cls) {
    return Py_TYPE(inst) == (PyTypeObject *)cls;
}


static PyObject *resolve_ref(module_state_t *module_state, PyObject *refs,
                             PyObject *t) {
    while (is_type(t, module_state->common_Ref)) {
        t = PyObject_GetItem(refs, t);
        if (!t)
            return NULL;
        Py_DECREF(t);
    }
    return t;
}


static ssize_t encode_boolean(hat_buff_t *buff, PyObject *value) {
    int v = PyObject_IsTrue(value);
    return hat_sbs_encode_boolean(buff, v);
}


static ssize_t encode_integer(hat_buff_t *buff, PyObject *value) {
    long v = PyLong_AsLong(value);
    if (v == -1 && PyErr_Occurred())
        return -1;
    return hat_sbs_encode_integer(buff, v);
}


static ssize_t encode_float(hat_buff_t *buff, PyObject *value) {
    double v = PyFloat_AsDouble(value);
    if (v == -1.0 && PyErr_Occurred())
        return -1;
    return hat_sbs_encode_float(buff, v);
}


static ssize_t encode_string(hat_buff_t *buff, PyObject *value) {
    Py_ssize_t v_len;
    const char *v = PyUnicode_AsUTF8AndSize(value, &v_len);
    if (!v)
        return -1;
    return hat_sbs_encode_string(buff, (uint8_t *)v, v_len);
}


static ssize_t encode_bytes(hat_buff_t *buff, PyObject *value) {
    char *v;
    Py_ssize_t v_len;
    if (PyBytes_AsStringAndSize(value, &v, &v_len) == -1)
        return -1;
    return hat_sbs_encode_bytes(buff, v, v_len);
}


static ssize_t encode_array(hat_buff_t *buff, module_state_t *module_state,
                            PyObject *refs, PyObject *t, PyObject *value) {
    size_t init_buff_pos = (buff ? buff->pos : 0);

    Py_ssize_t len = PyList_Size(value);
    if (len < 0)
        return -1;

    PyObject *item_type = PyObject_GetAttrString(t, "t");
    if (!item_type)
        return -1;
    Py_DECREF(item_type);

    size_t result = hat_sbs_encode_array_header(buff, len);

    for (size_t i = 0; i < len; ++i) {
        PyObject *item = PyList_GetItem(value, i);
        if (!item) {
            if (buff)
                buff->pos = init_buff_pos;
            return -1;
        }

        hat_buff_t *item_buff = (result ? NULL : buff);
        ssize_t item_result =
            encode_generic(item_buff, module_state, refs, item_type, item);
        if (item_result < 0) {
            if (buff)
                buff->pos = init_buff_pos;
            return -1;
        }

        result += item_result;
    }

    if (buff && result) {
        result += buff->pos - init_buff_pos;
        buff->pos = init_buff_pos;
    }

    return result;
}


static ssize_t encode_tuple(hat_buff_t *buff, module_state_t *module_state,
                            PyObject *refs, PyObject *t, PyObject *value) {
    size_t init_buff_pos = (buff ? buff->pos : 0);

    PyObject *t_entries = PyObject_GetAttrString(t, "entries");
    if (!t_entries)
        return -1;
    Py_DECREF(t_entries);

    Py_ssize_t size = PyList_Size(t_entries);
    if (size < 0)
        return -1;

    size_t result = 0;

    for (size_t i = 0; i < size; ++i) {
        PyObject *entry_name_type = PyList_GetItem(t_entries, i);
        if (!entry_name_type) {
            if (buff)
                buff->pos = init_buff_pos;
            return -1;
        }

        PyObject *entry_name = PyTuple_GetItem(entry_name_type, 0);
        PyObject *entry_type = PyTuple_GetItem(entry_name_type, 1);
        if (!entry_name || !entry_type) {
            if (buff)
                buff->pos = init_buff_pos;
            return -1;
        }

        PyObject *entry = PyDict_GetItem(value, entry_name);
        if (!entry) {
            if (buff)
                buff->pos = init_buff_pos;
            return -1;
        }

        hat_buff_t *entry_buff = (result ? NULL : buff);
        ssize_t entry_result =
            encode_generic(entry_buff, module_state, refs, entry_type, entry);
        if (entry_result < 0) {
            if (buff)
                buff->pos = init_buff_pos;
            return -1;
        }

        result += entry_result;
    }

    if (buff && result) {
        result += buff->pos - init_buff_pos;
        buff->pos = init_buff_pos;
    }

    return result;
}


static ssize_t encode_union(hat_buff_t *buff, module_state_t *module_state,
                            PyObject *refs, PyObject *t, PyObject *value) {
    PyObject *t_entries = PyObject_GetAttrString(t, "entries");
    if (!t_entries)
        return -1;
    Py_DECREF(t_entries);

    Py_ssize_t size = PyList_Size(t_entries);
    if (size < 0)
        return -1;

    if (!size)
        return 0;

    PyObject *entry_name = PyTuple_GetItem(value, 0);
    if (!entry_name)
        return -1;

    PyObject *entry = PyTuple_GetItem(value, 1);
    if (!entry)
        return -1;

    size_t id;
    PyObject *entry_type = NULL;
    for (id = 0; id < size; ++id) {
        PyObject *temp = PyList_GetItem(t_entries, id);
        if (!temp)
            return -1;

        PyObject *temp_name = PyTuple_GetItem(temp, 0);
        if (!temp_name)
            return -1;

        if (PyUnicode_Compare(entry_name, temp_name)) {
            if (PyErr_Occurred())
                return -1;
            continue;
        }

        entry_type = PyTuple_GetItem(temp, 1);
        if (!entry_type)
            return -1;
        break;
    }
    if (!entry_type)
        return -1;

    size_t init_buff_pos = (buff ? buff->pos : 0);

    size_t result = hat_sbs_encode_union_header(buff, id);

    hat_buff_t *entry_buff = (result ? NULL : buff);
    ssize_t entry_result =
        encode_generic(entry_buff, module_state, refs, entry_type, entry);
    if (entry_result < 0) {
        if (buff)
            buff->pos = init_buff_pos;
        return -1;
    }
    result += entry_result;

    if (buff && result) {
        result += buff->pos - init_buff_pos;
        buff->pos = init_buff_pos;
    }

    return result;
}


static PyObject *decode_boolean(hat_buff_t *buff) {
    bool value;
    if (hat_sbs_decode_boolean(buff, &value))
        return NULL;
    return PyBool_FromLong(value);
}


static PyObject *decode_integer(hat_buff_t *buff) {
    int64_t value;
    if (hat_sbs_decode_integer(buff, &value))
        return NULL;
    return PyLong_FromLong(value);
}


static PyObject *decode_float(hat_buff_t *buff) {
    double value;
    if (hat_sbs_decode_float(buff, &value))
        return NULL;
    return PyFloat_FromDouble(value);
}


static PyObject *decode_string(hat_buff_t *buff) {
    uint8_t *value;
    size_t value_len;
    if (hat_sbs_decode_string(buff, &value, &value_len))
        return NULL;
    return PyUnicode_DecodeUTF8(value, value_len, NULL);
}


static PyObject *decode_bytes(hat_buff_t *buff) {
    uint8_t *value;
    size_t value_len;
    if (hat_sbs_decode_bytes(buff, &value, &value_len))
        return NULL;
    return PyBytes_FromStringAndSize(value, value_len);
}


static PyObject *decode_array(hat_buff_t *buff, module_state_t *module_state,
                              PyObject *refs, PyObject *t) {
    size_t len;
    if (hat_sbs_decode_array_header(buff, &len))
        return NULL;

    PyObject *item_type = PyObject_GetAttrString(t, "t");
    if (!item_type)
        return NULL;
    Py_DECREF(item_type);

    PyObject *result = PyList_New(len);
    for (size_t i = 0; result && i < len; ++i) {
        PyObject *item = decode_generic(buff, module_state, refs, item_type);

        if (item && PyList_SetItem(result, i, item))
            Py_CLEAR(item);

        if (!item)
            Py_CLEAR(result);
    }

    return result;
}


static PyObject *decode_tuple(hat_buff_t *buff, module_state_t *module_state,
                              PyObject *refs, PyObject *t) {
    PyObject *t_entries = PyObject_GetAttrString(t, "entries");
    if (!t_entries)
        return NULL;
    Py_DECREF(t_entries);

    Py_ssize_t size = PyList_Size(t_entries);
    if (size < 0)
        return NULL;

    if (!size) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    PyObject *result = PyDict_New();
    for (size_t i = 0; result && i < size; ++i) {
        PyObject *entry_name_type = PyList_GetItem(t_entries, i);
        if (!entry_name_type) {
            Py_CLEAR(result);
            break;
        }

        PyObject *entry_name = PyTuple_GetItem(entry_name_type, 0);
        PyObject *entry_type = PyTuple_GetItem(entry_name_type, 1);
        if (!entry_name || !entry_type) {
            Py_CLEAR(result);
            break;
        }

        PyObject *entry = decode_generic(buff, module_state, refs, entry_type);
        if (!entry) {
            Py_CLEAR(result);
            break;
        }

        if (PyDict_SetItem(result, entry_name, entry))
            Py_CLEAR(result);

        Py_DECREF(entry);
    }

    return result;
}


static PyObject *decode_union(hat_buff_t *buff, module_state_t *module_state,
                              PyObject *refs, PyObject *t) {
    PyObject *t_entries = PyObject_GetAttrString(t, "entries");
    if (!t_entries)
        return NULL;
    Py_DECREF(t_entries);

    Py_ssize_t size = PyList_Size(t_entries);
    if (size < 0)
        return NULL;

    if (!size) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    size_t id;
    if (hat_sbs_decode_union_header(buff, &id))
        return NULL;

    PyObject *entry_name_type = PyList_GetItem(t_entries, id);
    if (!entry_name_type)
        return NULL;

    PyObject *entry_name = PyTuple_GetItem(entry_name_type, 0);
    PyObject *entry_type = PyTuple_GetItem(entry_name_type, 1);
    if (!entry_name || !entry_type)
        return NULL;

    PyObject *entry = decode_generic(buff, module_state, refs, entry_type);
    if (!entry)
        return NULL;
    Py_INCREF(entry_name);

    PyObject *result = PyTuple_New(2);
    if (!result)
        goto cleanup;

    if (PyTuple_SetItem(result, 0, entry_name))
        goto cleanup;
    entry_name = NULL;

    if (PyTuple_SetItem(result, 1, entry))
        goto cleanup;
    entry = NULL;

cleanup:

    Py_XDECREF(entry_name);
    Py_XDECREF(entry);

    if (PyErr_Occurred())
        Py_CLEAR(result);

    return result;
}


static ssize_t encode_generic(hat_buff_t *buff, module_state_t *module_state,
                              PyObject *refs, PyObject *t, PyObject *value) {
    int result;

    t = resolve_ref(module_state, refs, t);
    if (!t)
        return -1;

    if (is_type(t, module_state->common_BooleanType))
        return encode_boolean(buff, value);

    if (is_type(t, module_state->common_IntegerType))
        return encode_integer(buff, value);

    if (is_type(t, module_state->common_FloatType))
        return encode_float(buff, value);

    if (is_type(t, module_state->common_StringType))
        return encode_string(buff, value);

    if (is_type(t, module_state->common_BytesType))
        return encode_bytes(buff, value);

    if (is_type(t, module_state->common_ArrayType))
        return encode_array(buff, module_state, refs, t, value);

    if (is_type(t, module_state->common_TupleType))
        return encode_tuple(buff, module_state, refs, t, value);

    if (is_type(t, module_state->common_UnionType))
        return encode_union(buff, module_state, refs, t, value);

    PyErr_SetNone(PyExc_ValueError);
    return -1;
}


static PyObject *decode_generic(hat_buff_t *buff, module_state_t *module_state,
                                PyObject *refs, PyObject *t) {
    int result;

    t = resolve_ref(module_state, refs, t);
    if (!t)
        return NULL;

    if (is_type(t, module_state->common_BooleanType))
        return decode_boolean(buff);

    if (is_type(t, module_state->common_IntegerType))
        return decode_integer(buff);

    if (is_type(t, module_state->common_FloatType))
        return decode_float(buff);

    if (is_type(t, module_state->common_StringType))
        return decode_string(buff);

    if (is_type(t, module_state->common_BytesType))
        return decode_bytes(buff);

    if (is_type(t, module_state->common_ArrayType))
        return decode_array(buff, module_state, refs, t);

    if (is_type(t, module_state->common_TupleType))
        return decode_tuple(buff, module_state, refs, t);

    if (is_type(t, module_state->common_UnionType))
        return decode_union(buff, module_state, refs, t);

    PyErr_SetNone(PyExc_ValueError);
    return NULL;
}


static PyObject *encode(PyObject *self, PyObject *args) {
    module_state_t *module_state = PyModule_GetState(self);
    if (!module_state)
        return NULL;

    PyObject *refs;
    PyObject *t;
    PyObject *value;

    if (!PyArg_ParseTuple(args, "OOO", &refs, &t, &value))
        return NULL;

    ssize_t data_size = encode_generic(NULL, module_state, refs, t, value);
    if (data_size < 0)
        return NULL;

    PyObject *data = PyBytes_FromStringAndSize(NULL, data_size);
    if (!data)
        return NULL;

    hat_buff_t buff = {
        .data = PyBytes_AsString(data), .size = data_size, .pos = 0};

    if (!buff.data) {
        Py_DECREF(data);
        return NULL;
    }

    ssize_t result = encode_generic(&buff, module_state, refs, t, value);
    if (result || hat_buff_available(&buff)) {
        Py_DECREF(data);
        return NULL;
    }

    return data;
}


static PyObject *decode(PyObject *self, PyObject *args) {
    module_state_t *module_state = PyModule_GetState(self);
    if (!module_state)
        return NULL;

    PyObject *refs;
    PyObject *t;
    PyObject *data;

    if (!PyArg_ParseTuple(args, "OOO", &refs, &t, &data))
        return NULL;

    if (!PyMemoryView_Check(data))
        return NULL;

    hat_buff_t buff = {.data = PyMemoryView_GET_BUFFER(data)->buf,
                       .size = PyMemoryView_GET_BUFFER(data)->len,
                       .pos = 0};

    return decode_generic(&buff, module_state, refs, t);
}


static int module_clear(PyObject *self) {
    if (!self)
        return 0;
    module_state_t *module_state = PyModule_GetState(self);
    Py_CLEAR(module_state->common_Ref);
    Py_CLEAR(module_state->common_BooleanType);
    Py_CLEAR(module_state->common_IntegerType);
    Py_CLEAR(module_state->common_FloatType);
    Py_CLEAR(module_state->common_StringType);
    Py_CLEAR(module_state->common_BytesType);
    Py_CLEAR(module_state->common_ArrayType);
    Py_CLEAR(module_state->common_TupleType);
    Py_CLEAR(module_state->common_UnionType);
    return 0;
}


PyMethodDef module_methods[] = {{"encode", encode, METH_VARARGS, NULL},
                                {"decode", decode, METH_VARARGS, NULL},
                                {NULL, NULL, 0, NULL}};


struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT,
                                 "_cserializer",
                                 NULL,
                                 sizeof(module_state_t),
                                 module_methods,
                                 NULL,
                                 NULL,
                                 module_clear,
                                 NULL};


PyMODINIT_FUNC PyInit__cserializer() {
    PyObject *module = PyModule_Create(&module_def);
    if (!module)
        return NULL;

    module_state_t *module_state = PyModule_GetState(module);
    module_state->common_Ref = NULL;
    module_state->common_BooleanType = NULL;
    module_state->common_IntegerType = NULL;
    module_state->common_FloatType = NULL;
    module_state->common_StringType = NULL;
    module_state->common_BytesType = NULL;
    module_state->common_ArrayType = NULL;
    module_state->common_TupleType = NULL;
    module_state->common_UnionType = NULL;

    PyObject *common = PyImport_ImportModule("hat.sbs.common");
    if (!common)
        goto cleanup;

    PyObject *common_dict = PyModule_GetDict(common);
    if (!common_dict)
        goto cleanup;

    module_state->common_Ref = PyMapping_GetItemString(common_dict, "Ref");
    if (!module_state->common_Ref)
        goto cleanup;

    module_state->common_BooleanType =
        PyMapping_GetItemString(common_dict, "BooleanType");
    if (!module_state->common_BooleanType)
        goto cleanup;

    module_state->common_IntegerType =
        PyMapping_GetItemString(common_dict, "IntegerType");
    if (!module_state->common_IntegerType)
        goto cleanup;

    module_state->common_FloatType =
        PyMapping_GetItemString(common_dict, "FloatType");
    if (!module_state->common_FloatType)
        goto cleanup;

    module_state->common_StringType =
        PyMapping_GetItemString(common_dict, "StringType");
    if (!module_state->common_StringType)
        goto cleanup;

    module_state->common_BytesType =
        PyMapping_GetItemString(common_dict, "BytesType");
    if (!module_state->common_BytesType)
        goto cleanup;

    module_state->common_ArrayType =
        PyMapping_GetItemString(common_dict, "ArrayType");
    if (!module_state->common_ArrayType)
        goto cleanup;

    module_state->common_TupleType =
        PyMapping_GetItemString(common_dict, "TupleType");
    if (!module_state->common_TupleType)
        goto cleanup;

    module_state->common_UnionType =
        PyMapping_GetItemString(common_dict, "UnionType");
    if (!module_state->common_UnionType)
        goto cleanup;

cleanup:

    Py_XDECREF(common);

    if (PyErr_Occurred()) {
        Py_XDECREF(module_state->common_Ref);
        Py_XDECREF(module_state->common_BooleanType);
        Py_XDECREF(module_state->common_IntegerType);
        Py_XDECREF(module_state->common_FloatType);
        Py_XDECREF(module_state->common_StringType);
        Py_XDECREF(module_state->common_BytesType);
        Py_XDECREF(module_state->common_ArrayType);
        Py_XDECREF(module_state->common_TupleType);
        Py_XDECREF(module_state->common_UnionType);
        Py_CLEAR(module);
    }

    return module;
}
