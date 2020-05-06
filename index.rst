:tocdepth: 1

.. sectnum::

.. note::

   **This technote is not yet published.**

.. _abstract:

Abstract
========

This technote summarizes the authentication and authorization needs for the Rubin Science Platform, discusses trade-offs between possible implementation strategies, and proposes a design based on identity-only JWTs and a separate authorization and user metadata service.

This is neither a complete risk assessment nor a detailed technical specification.
Those topics will be covered in subsequent documents.

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
- Authentication to API services from the user's local system using HTTP Basic, as a fallback for legacy software that only understands that authentication mechanism.
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
All aspects of this design are discussed in more detail in :ref:`discuss`, including alternatives and trade-offs.

This is a high-level description of the design.
Specific details (choices of encryption protocols, cookie formats, session storage schemas, and so forth) will be spelled out in subsequent documents.

As a general design point affecting every design area, TLS is required for all traffic between the user and the Rubin Science Platform.
Communications internal to the Rubin Science Platform need not use TLS provided that they happen only on a restricted private network specific to the Rubin Science Platform deployment.

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

API calls are authenticated with opaque bearer tokens, by default via the HTTP Bearer authentication mechanism.
To allow use of legacy software that only supports HTTP Basic authentication, they may also be used as the username field of an HTTP Basic ``Authorization`` header.

Interally, these opaque bearer tokens will be replaced with a :abbr:`JSON Web Token (JWT)`.
Internal services will therefore expect and consume JWTs, and internal service-to-service calls will use JWTs for authentication.
These JWTs will contain only identity information, not group or scope information.
See :ref:`groups` for more details on group management.
The opaque bearer token will be replaced with a JWT by the authentication handler that sits in front of each protected service.

Users can list their bearer tokens, create new ones, or delete them.
User-created bearer tokens do not expire.
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

.. _discuss:

Design discussion
=================

.. _discuss-api-auth:

API authentication
------------------

There are four widely-deployed choices for API authentication:

#. HTTP Basic with username and password
#. Opaque bearer tokens
#. JWTs
#. Client TLS certificates

The first two are roughly equivalent except that HTTP Basic imposes more length restrictions on the authenticator, triggers browser prompting behavior, and has been replaced by bearer token authentication in general best practices for web services.
Client TLS certificates provide the best security since they are not vulnerable to man-in-the-middle attacks, but are awkward to manage on the client side and cannot be easily cut-and-pasted.
TLS certificates also cannot be used in HTTP Basic fallback situations with software that only supports that authentication mechanism.

Opaque bearer tokens and JWTs are therefore the most appealing.
However, we expect to have to support HTTP Basic as a fallback for some legacy software that only understands that authentication mechanism.

JWTs are standardized and widely supported by both third-party software and by libraries and other tools, and do not inherently require a backing data store.
However, JWTs are necessarily long.
An absolutely minimal JWT (only a ``sub`` claim with a single-character identity) using the ``ES256`` algorithm to minimize the signature size is 181 octets.
With a reasonable set of claims for best-practice usage (``aud``, ``iss``, ``iat``, ``exp``, ``sub``, ``jti``, and ``scope``), again using the ``ES256`` algorithm, the JWT is around 450 octets.

Length matters because HTTP requests have to pass through various clients, libraries, gateways, and web servers, many of which impose limits on HTTP header length, either in aggregate or for individual headers.
Multiple services often share the same cookie namespace and compete for those limited resources.
The constraints become more severe when supporting HTTP Basic.
The username and password fields of the HTTP Basic ``Authorization`` header are often limited to 256 octets, and some software imposes limits as small as 64 octets under the assumption that these fields only need to hold traditional, short usernames and passwords.
Even minimal JWTs are therefore dangerously long, and best-practice JWTs are too long to use with HTTP Basic authentication.

Opaque bearer tokens avoid this problem.
An opaque token need only be long enough to defeat brute force searches, for which 128 bits of randomness are sufficient.
For various implementation reasons it is often desirable to have a random token ID and a separate random secret, and to add a standard prefix to all opaque tokens, but even with this taken into account, a token with a four-octet identifying prefix and two 128-bit random segments, encoded in URL-safe base64 encoding, is only 49 octets.

The HTTP Basic requirement only applies to the request from the user to the authentication gateway for the Rubin Science Platform.
The length constraints similarly matter primarily for the HTTP Basic requirement and for authentication from web browsers, which may have a multitude of cookies and other necessary headers.
Within the Rubin Science Platform, JWTs are appealing because they are more transparent and do not require querying stored state to interpret.

This technote therefore proposes a hybrid model.
Authentication from the user's system (and, as discussed in :ref:`discuss-browser-auth`, web browsers) should use opaque bearer tokens.
Those opaque tokens should be converted to JWTs by a service that sits in front of each service that requires authentication.
API services should receive JWTs, and use JWTs for internal service-to-service authentication.

There are two options for the notebook aspect: use opaque bearer tokens so that identical authenticators are used in the notebook and on the user's local system, or use JWTs since the notebook aspect doesn't have the problems that require shorter tokens.
Using JWTs has the benefit of not requiring state or the bottleneck of a session database when authenticating API calls from the notebook aspect, which are expected to be the bulk of API traffic handled by the Rubin Science Platform.
However, the inconsistency between the tokens used by code running in the notebook and code running on the user's system has the potential to create confusing differences in behavior, and introduces additional complexity.
Scaling problems are generally easier to solve than user confusion problems; this technote therefore recommends using opaque bearer tokens and the same authentication gateway and mapping layer for both direct user calls and notebook aspect calls.

This also prompts the question: Why use JWTs at all?
Why not use opaque bearer tokens for all internal communication, and issue them as needed to internal components for service-to-service calls?

There are three reasons to retain JWTs as the representation of authentication to the service itself:

#. Some third-party services may consume JWTs directly and expect to be able to validate them.
#. If a user API call sets off a cascade of numerous internal API calls, avoiding the need to consult a data store to validate opaque tokens could improve performance.
   JWTs can be verified directly without needing any state other than the (relatively unchanging) public signing key.
#. JWTs are apparently becoming the standard protocol for API web authentication.
   Preserving a JWT component to the Rubin Science Platform will allow us to interoperate with future services, possibly outside the Rubin Science Platform, that require JWT-based authentication.
   It also preserves the option to drop opaque bearer tokens entirely if the header length and HTTP Basic requirements are relaxed in the future (by, for example, no longer supporting older software with those limitations).

These justifications are fairly weak.
Dropping JWTs from the design entirely and using only opaque bearer tokens interpreted by a single component with a private backing store of session information is worth consideration.

.. _discuss-browser-auth:

Web browser authentication
--------------------------

.. _open-questions:

Open questions
==============

#. Will the Rubin Science Platform need to provide shared relational database storage to users with authorization rules that they can control (for example, allowing specific collaborators to access some of their tables)?
#. Will the Rubin Science Platform need to provide an object store to users with authorization rules that they can control (for example, allowing access to their objects to specific collaborators).
#. How do we handle changes in institutional affiliation?
   Suppose, for instance, a user has access via the University of Washington, and has also configured GitHub as an authentication provider because that's more convenient for them.
   Now suppose the user's affiliation with the University of Washington ends.
   If the user continues to authenticate via GitHub, how do we know to update their access control information based on that change of affiliation?

.. _references:

References
==========

- `JSON Web Token (JWT) <https://tools.ietf.org/html/rfc7519`
- `OAuth 2.0: Bearer Token Usage <https://tools.ietf.org/html/rfc6750>`
