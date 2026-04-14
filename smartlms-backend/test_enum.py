import sqlalchemy
import enum
class UserRole(str, enum.Enum): 
    ADMIN='admin'
    TEACHER='teacher'
    STUDENT='student'
e = sqlalchemy.Enum(UserRole)
print(e.enums)
