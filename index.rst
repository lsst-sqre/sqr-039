:tocdepth: 1

.. sectnum::

.. note::

   **This technote is not yet published.**

.. _abstract:

Abstract
========

This note summarizes the authentication and authorization needs for the Rubin Science Platform, discusses trade-offs between possible implementation strategies, and proposes a design based on identity-only JWTs and a separate authorization and user metadata service.

.. _problem:

Problem statement
=================

The Rubin Science Platform consists of a notebook aspect and a portal aspect accessible via a web browser, APIs accessible programmatically, and supporting services underlying those components such as user home directories and shared file system space.
Science platform users will come from a variety of participating institutions and may be located anywhere on the Internet.
Primary user authentication will be federated and thus delegated to the user's member institution.

The following authentication use cases must be supported:

- Initial user authentication via federated authentication by their home institution, using a web browser.
- Ongoing web browser authentication while the user interacts with the notebook or portal aspects.
- Authentication of API calls from programs running on the user's local system to services provided by the Rubin Science Platform.
- Authentication of API calls from the notebook aspect to other services within the Rubin Science Platform.
- Authentication of some mechanism for users to copy files from their local system into the user home directories and shared file systems used by the notebook aspect.

We want to enforce the following authorization boundaries:

- Limit access to the web interface (the notebook and portal aspects) to authorized project users.
- Limit access to some classes of data to only users authorized to access that data.
- Limit access to administrative and maintenance interfaces to project employees.
- Limit access to home directories to the user who owns the home directory and platform administrators.
- Limit access to shared collaborative file systems to the users authorized by the owner of the space.
  This in turn implies a self-serve group system so that users can create ad hoc groups and use them to share files with specific collaborators.
- Users can create long-lived tokens for API access.

.. _design:

Proposed design
===============

This is a proposed design for authentication and authorization that meets the above requirements.
All aspects of this design are discussed in more detail below, including alternatives and trade-offs.

This is a high-level description of the design.
Specific details (choices of encryption protocols, cookie formats, session storage schemas, and so forth) will be spelled out in subsequent documents.

.. _initial-auth:

Initial user authentication
---------------------------

Initial user authentication will be done via CILogon using a web browser.
CILogon will be used as an OpenID Connect provider, so the output from that authentication process will be a JWT issued by CILogon and containing the user's identity information.

The CILogon-provided identity will be mapped to a Rubin Science Platform user.
Users will be able to associate multiple CILogon identities with the same Rubin Science Platform user.
For example, a user may wish to sometimes authenticate using GitHub as an identity provider and at other times use the authentication system of their home institution.
They will be able to map both authentication paths to the same user and thus the same access, home directory, and permissions.

Additional metadata about the user (full name, UID, contact email address, GitHub identity if any) will be stored by the Rubin Science Platform and associated with those CILogon identities.
The UID will be assigned internally rather than reusing a UID provided by CILogon.
Other attributes may be initially seeded from CILogon information, but the user will then be able to change them as they wish.

After CILogon authentication, the Rubin Science Platform will create a session for that user in Redis and set a cookie pointing to that session.
The cookie and session will be used for further web authentication from that browser.
Each deployment of the Rubin Science Platform will use separate sessions and session keys, and thus require separate web browser authentication.

.. _api-auth:

API authentication
------------------

For internal authentication from the notebook aspect to other Rubin Science Platform services, the notebook will be issued a JWT based on the user's CILogon authentication.
This JWT will contain only identity information, not group or scope information.
See :ref:`groups` for more details on group management.

For external authentication to APIs, users can create new access tokens associated with their account.
They can be used as bearer tokens to access APIs.
To allow use of legacy software that only supports HTTP Basic authentication, they may also be used as the username field of an HTTP Basic ``Authorization`` header.
These access tokens internally map to a JWT similar to the JWT used by the notebook aspect, and will be replaced with the underlying JWT by the authentication handler so that services see the JWT form.

These access tokens are not accepted as an authentication mechanism to web interfaces such as the notebook or portal aspect, or other internal pages such as the page to manage identity provider associations or group membership.

Users can list their access tokens, create new ones, or delete them.
These access tokens do not expire.
Administrators can invalidate them if necessary (such as for security reasons).

.. _groups:

Group membership
----------------

Users will have group memberships, which will be used for access control and (depending on the storage platform) may be used to populate GID information.
Some group information may be based on the user's institutional affiliation.
Other groups will be self-service.
Users can create groups and add other users to those groups as they wish.
All groups will be assigned a unique GID for use within shared storage, assuming we use a storage backend that uses GIDs.

Group membership will not be encoded in JWTs or in the user's web session.
Instead, all Rubin Science Platform services will have access to a web service that, given a user's identity, will return the group membership for that user.
For services that only need simple authorization checks, this can optionally be done by the authentication handler that sits in front of the service.

.. _file-storage:

File storage
------------

Users of the notebook aspect will have a personal home directory and access to shared file space.
Users may create collaboration directories in the shared file space and limit access to groups, either platform-maintained groups or user-managed groups.
These file systems will be exposed inside the notebook aspect as POSIX directory structures using POSIX groups for access control.

To support this, the notebook aspect will, on notebook launch, retrieve the user's UID and their group memberships from a metadata service and use that information to set file system permissions appropriately.
If the file system backing store uses GIDs for access control (NFS, for example), those will be retrieved with the group membership from the metadata service.

Users will also want to easily copy files from their local system into file storage accessible by the notebook aspect, ideally via some implicit sync or shared file system that does not require an explicit copy command.
The exact mechanism for doing this is still to be determined, but will likely involve a server on the Rubin Science Platform side that accepts user credentials and then performs file operations with appropriate permissions as determined by the user's group membership.
User authentication for remote file system operations will be via the same access token as remote API calls.
See :ref:`api-auth`.

Open questions
==============

#. Will the Rubin Science Platform need to provide shared relational database storage to users with authorization rules that they can control (for example, allowing specific collaborators to access some of their tables)?
#. Will the Rubin Science Platform need to provide an object store to users with authorization rules that they can control (for example, allowing access to their objects to specific collaborators).
#. How do we handle changes in institutional affiliation?
   Suppose, for instance, a user has access via the University of Washington, and has also configured GitHub as an authentication provider because that's more convenient for them.
   Now suppose the user's affiliation with the University of Washington ends.
   If the user continues to authenticate via GitHub, how do we know to update their access control information based on that change of affiliation?
