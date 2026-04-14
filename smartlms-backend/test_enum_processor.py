import sqlalchemy
import enum

class UserRole(str, enum.Enum): 
    ADMIN='admin'
    TEACHER='teacher'
    STUDENT='student'

class DummyRow:
    role = 'ADMIN'

try:
    e = sqlalchemy.Enum(UserRole)
    print("lookup_by_key:", e.values_callable)
    # How does TypeProcessor handle it?
    processor = e.result_processor(None, 1)
    val = processor('ADMIN')
    print("Processed:", repr(val))
    print(val == UserRole.ADMIN)
except Exception as ex:
    print(ex)
