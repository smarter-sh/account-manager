"""Django ORM base model."""

from logging import getLogger

from django.core.exceptions import ValidationError
from django.db import models

logger = getLogger(__name__)


class TimestampedModel(models.Model):
    """
    Abstract base model for all Django ORM models in the Account Manager project, providing automatic.

    timestamp fields and utility methods.

    This class should be used as the base class for all models in the project to ensure
    consistent tracking of creation and modification times. It adds ``created_at`` and
    ``updated_at`` fields, and a validation hook.

    **Example Usage:**

    .. code-block:: python

        from am.lib.django.model_helpers import TimestampedModel

        class MyModel(TimestampedModel):
            name = models.CharField(max_length=100)

        # Creating an instance
        obj = MyModel.objects.create(name="Example")
        print(obj.created_at)  # Timestamp of creation
        print(obj.updated_at)  # Timestamp of last update

    **Parameters:**

    Inherits all parameters from ``django.db.models.Model``.

    .. note::

        - This class is abstract and will not create a database table by itself.
        - The ``validate()`` method is a stub and should be implemented in subclasses as needed.
        - The ``save()`` method enforces validation before saving, raising a detailed error if validation fails.

    .. important::

        - If you override ``save()``, ensure you call ``super().save(*args, **kwargs)`` to retain validation and timestamp behavior.
    """

    created_at = models.DateTimeField(auto_now_add=True, null=True, editable=False, db_index=True)
    """
    Timestamp indicating when the model instance was created.

    This field is automatically set to the current date and time when the instance is first created.
    It is indexed in the database for efficient querying.
    """
    updated_at = models.DateTimeField(auto_now=True, null=True, editable=False, db_index=True)
    """
    Timestamp indicating when the model instance was last updated.

    This field is automatically updated to the current date and time whenever the instance is saved.
    It is indexed in the database for efficient querying.
    """

    # pylint: disable=missing-class-docstring
    class Meta:
        abstract = True

    def validate(self):
        """
        Validate the model.

        .. attention::

            Currently a stub method; does not perform any validation.
            This breaks on AMAuthToken.objects.create()
        """
        # self.full_clean()
        # logger.warning("TimestampedModel().validate() called but not applied on %s", self.__class__.__name__)

    def save(self, *args, **kwargs):
        """
        Save the model instance to the database, performing validation before the actual save.

        This method overrides the default ``save()`` behavior of Django models to ensure that
        the model is validated by calling :meth:`validate` before any data is written to the database.
        If validation fails, a :exc:`django.core.exceptions.ValidationError` is raised with detailed
        information about the error and the model class.

        Parameters
        ----------
        *args
            Positional arguments passed to the parent ``save()`` method. These are forwarded to Django's ORM.
        **kwargs
            Keyword arguments passed to the parent ``save()`` method. These are forwarded to Django's ORM.

        Examples
        --------
        .. code-block:: python

            obj = MyModel(name="Example")
            obj.save()  # Will call validate() before saving

        .. note::

            - The :meth:`validate` method is intended to be overridden in subclasses to provide custom validation logic.
            - If :meth:`validate` raises a :exc:`ValidationError`, the save operation is aborted and the error is propagated.
            - The error message names the model class. It leaves out field values, which may hold personal data or secrets.

        .. important::

            - If you override this method in a subclass, always call ``super().save(*args, **kwargs)`` to retain validation and timestamp functionality.
            - If validation fails, no data will be saved to the database.
        """
        try:
            self.validate()
        except ValidationError as e:
            raise ValidationError(
                f"TimestampedModel().save() validation error: {e} | model={self.__class__.__name__}"
            ) from e
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.__class__.__name__}(pk={self.pk})"
