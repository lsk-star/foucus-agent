from pydantic import BaseModel, ConfigDict, Field


class SchemaProviderSchema(BaseModel):
    """SchemaProvider 模块的通用数据模型基类。请按业务增加字段。"""

    model_config = ConfigDict(from_attributes=True)

    # 示例：name: str
    # 生成器不猜测业务字段，避免生成错误的数据契约。


class Column(BaseModel):
    """表列定义。"""

    model_config = ConfigDict(from_attributes=True)

    name: str
    type: str
    comment: str
    key: str | None = None
    nullable: bool = True


class ForeignKey(BaseModel):
    """外键关系。"""

    model_config = ConfigDict(from_attributes=True)

    column: str
    ref_table: str = Field(alias="refTable")
    ref_column: str = Field(alias="refColumn")


class Table(BaseModel):
    """数据表定义。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    name: str
    description: str
    columns: list[Column]
    foreign_keys: list[ForeignKey] = Field(default_factory=list, alias="foreignKeys")


class GlossaryTerm(BaseModel):
    """业务术语定义。"""

    model_config = ConfigDict(from_attributes=True)

    term: str
    description: str
    sql_fragment: str = Field(alias="sqlFragment")
    synonyms: list[str] = Field(default_factory=list)


class FkDesc(BaseModel):
    """外键描述，记录本表某列引用的其它表列。"""

    model_config = ConfigDict(from_attributes=True)

    column: str
    ref_table: str
    ref_column: str


class TableEntry(BaseModel):
    """表摘要条目，包含表名、描述、外键描述及双向关联的其它表（去重排序）。"""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: str
    foreign_keys: list[FkDesc]
    related_tables: list[str]


class SchemaCatalog(BaseModel):
    """Schema 目录，包含所有表定义和业务术语。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    tables: list[Table]
    glossary: list[GlossaryTerm]