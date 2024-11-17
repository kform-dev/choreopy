from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

def clean_description(description: str) -> str:
    """Strips leading and trailing whitespace and condenses all internal whitespace to a single space."""
    return ' '.join(description.strip().split())

class Resource(BaseModel):
    @classmethod
    def schema(cls, **kwargs):
        base_schema = super().schema(**kwargs)
        if cls.__doc__:
            # Strip out excess whitespace and add the docstring as the schema description
            base_schema['description'] = ' '.join(cls.__doc__.strip().split())
        return base_schema
    
    apiVersion: str = Field(
        None, 
        description=clean_description('''
            APIVersion defines the versioned schema of this representation of an object.
            Servers should convert recognized schemas to the latest internal value, and may
            reject unrecognized values. More info:
            https://git.k8s.io/community/contributors/devel/sig-architecture/api-conventions.md#resources
        '''),
    )
    kind: str = Field(
        None,
        description=clean_description('''
            Kind is a string value representing the REST resource this object represents.
            Servers may infer this from the endpoint the client submits requests to.
            Cannot be updated. In CamelCase. More info:
            https://git.k8s.io/community/contributors/devel/sig-architecture/api-conventions.md#types-kinds
        ''')
    )
    metadata: object = Field(
        None,
        json_schema_extra={
            "type": "object",
        }
    )

class Condition(BaseModel):
    lastTransitionTime: datetime = Field(
        description=clean_description('''
            lastTransitionTime is the last time the condition
            transitioned from one status to another. This should be when
            the underlying condition changed.  If that is not known, then
            using the time when the API field changed is acceptable.
        '''),
    )
    message: str = Field(
        description=clean_description('''
            message is a human readable message indicating
            details about the transition. This may be an empty string.
        '''),
        max_length=32768,
    )
    observedGeneration: int = Field(
        None,
        description=clean_description('''
            observedGeneration represents the .metadata.generation
            that the condition was set based upon. For instance, if .metadata.generation
            is currently 12, but the .status.conditions[x].observedGeneration
            is 9, the condition is out of date with respect to the current
            state of the instance.
        '''),
        min=0,
        format="int64",
    )
    reason: str = Field(
        description=clean_description('''
            reason contains a programmatic identifier indicating
            the reason for the condition's last transition. Producers
            of specific condition types may define expected values and
            meanings for this field, and whether the values are considered
            a guaranteed API. The value should be a CamelCase string.
            This field may not be empty.
        '''),
        max_length=1024,
        min_length=1,
        pattern="^[A-Za-z]([A-Za-z0-9_,:]*[A-Za-z0-9_])?$",
    )
    status:  Literal["True", "False", "unknown"] = Field(
        description=clean_description('''
            status of the condition, one of True, False, Unknown.
        '''),
    )
    type: str = Field(
        description=clean_description('''
            type of condition in CamelCase or in foo.example.com/CamelCase.
            --- Many .condition.type values are consistent across resources
            like Available, but because arbitrary conditions can be useful
            (see .node.status.conditions), the ability to deconflict is
            important. The regex it matches is (dns1123SubdomainFmt/)?(qualifiedNameFmt)
        '''),
        max_length=316,
        pattern="^([a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*/)?(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])$",
    )