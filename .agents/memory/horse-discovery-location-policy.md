---
name: Horse discovery location policy
description: Product boundaries for private member horse and stable discovery locations.
---

Horse and stable locations are private discovery inputs. Do not expose their exact addresses or coordinates publicly or add them to analytics, search-history payloads, or URLs. A horse identifier may restore the directory selection, but must be resolved against current ownership and saved location data.

Location is optional and must not become a profile-completion requirement. Horse owners without stable-management access may enter a custom horse location; this does not entitle them to manage a stable.

**Why:** The user explicitly scoped horse-location discovery as private and optional, preserving existing stable-management permissions and historical unlocated horses.

**How to apply:** Keep these boundaries when extending member forms, discovery, navigation, reporting, or analytics. Do not replace an unavailable selected horse location with browser location or an unfiltered result.
