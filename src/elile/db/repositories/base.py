"""Base repository with common CRUD operations.

Provides a generic repository pattern for SQLAlchemy models with
async support and tenant isolation.

Usage:
    from elile.db.repositories.base import BaseRepository

    class UserRepository(BaseRepository[User, UUID]):
        pass

    repo = UserRepository(db_session)
    user = await repo.get(user_id)
    users = await repo.list(limit=10, offset=0)
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from elile.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)
PKType = TypeVar("PKType", bound=UUID | int | str)


class BaseRepository(Generic[ModelType, PKType]):
    """Generic repository for SQLAlchemy models.

    Provides CRUD operations with async support. Subclass to add
    model-specific methods.

    Type Parameters:
        ModelType: The SQLAlchemy model class
        PKType: The type of the primary key (UUID, int, or str)

    Attributes:
        model: The model class
        db: The database session
    """

    model: type[ModelType]

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    def __init_subclass__(cls, **kwargs):
        """Extract model type from generic parameter."""
        super().__init_subclass__(**kwargs)
        # Get the model type from Generic parameter if specified
        for base in getattr(cls, "__orig_bases__", []):
            args = getattr(base, "__args__", None)
            if args and len(args) >= 1:
                first_arg = args[0]
                # Check if it's an actual class (not a TypeVar)
                if isinstance(first_arg, type) and issubclass(first_arg, Base):
                    cls.model = first_arg
                    break

    async def get(self, pk: PKType) -> ModelType | None:
        """Get a single record by primary key.

        Args:
            pk: Primary key value

        Returns:
            Model instance or None if not found
        """
        return await self.db.get(self.model, pk)

    async def get_or_raise(self, pk: PKType) -> ModelType:
        """Get a single record by primary key or raise.

        Args:
            pk: Primary key value

        Returns:
            Model instance

        Raises:
            ValueError: If record not found
        """
        result = await self.get(pk)
        if result is None:
            raise ValueError(f"{self.model.__name__} not found: {pk}")
        return result

    async def get_many(self, pks: Sequence[PKType]) -> list[ModelType]:
        """Get multiple records by primary keys.

        Args:
            pks: List of primary key values

        Returns:
            List of found models (may be fewer than requested if some not found)
        """
        if not pks:
            return []

        # Get the primary key column
        pk_col = self._get_pk_column()
        stmt = select(self.model).where(pk_col.in_(pks))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[ModelType]:
        """List records with pagination.

        Args:
            limit: Maximum records to return
            offset: Number of records to skip
            order_by: Column name to order by (default: primary key)
            descending: Sort in descending order

        Returns:
            List of model instances
        """
        stmt = select(self.model)

        # Apply ordering
        if order_by:
            col = getattr(self.model, order_by, None)
            if col is not None:
                stmt = stmt.order_by(col.desc() if descending else col)
        else:
            pk_col = self._get_pk_column()
            stmt = stmt.order_by(pk_col.desc() if descending else pk_col)

        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Count total records.

        Returns:
            Total count of records
        """
        pk_col = self._get_pk_column()
        stmt = select(func.count(pk_col))
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def create(self, obj: ModelType, *, commit: bool = True) -> ModelType:
        """Create a new record.

        Args:
            obj: Model instance to create
            commit: Whether to commit the transaction

        Returns:
            Created model instance
        """
        self.db.add(obj)
        if commit:
            await self.db.commit()
            await self.db.refresh(obj)
        else:
            await self.db.flush()
        return obj

    async def create_many(
        self, objs: Sequence[ModelType], *, commit: bool = True
    ) -> list[ModelType]:
        """Create multiple records.

        Args:
            objs: Model instances to create
            commit: Whether to commit the transaction

        Returns:
            List of created model instances
        """
        for obj in objs:
            self.db.add(obj)

        if commit:
            await self.db.commit()
            for obj in objs:
                await self.db.refresh(obj)
        else:
            await self.db.flush()

        return list(objs)

    async def update(
        self, obj: ModelType, updates: dict[str, Any], *, commit: bool = True
    ) -> ModelType:
        """Update a record with given values.

        Args:
            obj: Model instance to update
            updates: Dictionary of field: value to update
            commit: Whether to commit the transaction

        Returns:
            Updated model instance
        """
        for field, value in updates.items():
            if hasattr(obj, field):
                setattr(obj, field, value)

        if commit:
            await self.db.commit()
            await self.db.refresh(obj)
        else:
            await self.db.flush()

        return obj

    async def delete(self, obj: ModelType, *, commit: bool = True) -> None:
        """Delete a record.

        Args:
            obj: Model instance to delete
            commit: Whether to commit the transaction
        """
        await self.db.delete(obj)
        if commit:
            await self.db.commit()
        else:
            await self.db.flush()

    async def delete_by_pk(self, pk: PKType, *, commit: bool = True) -> bool:
        """Delete a record by primary key.

        Args:
            pk: Primary key value
            commit: Whether to commit the transaction

        Returns:
            True if deleted, False if not found
        """
        obj = await self.get(pk)
        if obj is None:
            return False

        await self.delete(obj, commit=commit)
        return True

    async def exists(self, pk: PKType) -> bool:
        """Check if a record exists.

        Args:
            pk: Primary key value

        Returns:
            True if exists, False otherwise
        """
        pk_col = self._get_pk_column()
        stmt = select(func.count(pk_col)).where(pk_col == pk)
        result = await self.db.execute(stmt)
        return (result.scalar() or 0) > 0

    def _get_pk_column(self):
        """Get the primary key column for this model.

        Returns:
            The primary key column

        Raises:
            ValueError: If no primary key found
        """
        # Get primary key from mapper
        mapper = self.model.__mapper__
        pk_cols = mapper.primary_key
        if not pk_cols:
            raise ValueError(f"No primary key found for {self.model.__name__}")
        return pk_cols[0]
