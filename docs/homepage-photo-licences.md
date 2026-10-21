# Homepage photograph source and licence record

Checked 2026-10-21. This is an internal evidence record, not a blanket legal
clearance or a claim that model/property releases have been obtained.

## Evidence and decision rule

The original `EquiConnected Home v2.dc.html` in the design archive
`attached_assets/Website_design_with_horseshoe_logo_1790683016956.zip` records the
CDN URLs below, along with the original credit strings. The archive is available
in Git history (it is no longer in the working tree). To inspect it:

```sh
git log --all -- attached_assets/Website_design_with_horseshoe_logo_1790683016956.zip
# Use a revision containing the file:
git show <revision>:attached_assets/Website_design_with_horseshoe_logo_1790683016956.zip > /tmp/home-reference.zip
```

The archive's image slots, the current section imports, and a visual inventory of
the local photos establish the source mapping. Public photo pages were then
located through Unsplash search pages, contributor profiles and related-photo
links. For every **verified** row, the individual photo page was opened and its
main image URL matched the archive's CDN photo identifier. Each of those pages
explicitly states **“Free to use under the Unsplash License”** and links to
https://unsplash.com/license. The source titles below are transcribed from those
pages; a title does not override the app's existing alternative text.

No photo bytes, crops, image descriptions, loading behavior or interactions were
changed. The two decorative statement details had no captions to remove.

## Applicable terms

- **Standard Unsplash:** https://unsplash.com/license, checked directly.
  The longform grant allows downloading, copying, modifying, distributing,
  performing and using images, including commercially, “without permission from
  or attributing the photographer or Unsplash.” Attribution is appreciated, not
  required. It excludes compiling images to replicate a competing service and
  selling unmodified images.
- **Unsplash+:** https://unsplash.com/plus/license, checked directly. This is a
  separate grant for images downloaded from an Unsplash+ subscription. Credits
  alone do not establish a subscription entitlement. None of the verified
  individual main-photo pages below identifies its image as Unsplash+; premium
  advertisements/related images on a free photo page are not that page's photo.
- **API:** https://help.unsplash.com/en/articles/2511245-unsplash-api-guidelines,
  checked directly. API integrations must attribute Unsplash and the photographer
  with a profile link, hotlink images and trigger download tracking. The checked
  prototype uses fixed CDN URLs in static image slots, and the current homepage
  uses bundled/static assets, not an Unsplash API image-picker/integration.
  Removal here relies on the independently verified public standard-licence
  pages, **not** on local hosting proving a licence or waiving API obligations.
  The historical download mechanism is not documented; this record does not
  certify compliance of any earlier API use. If a separate API agreement or
  acquisition restriction is discovered, reassess the affected credit.
- **Other rights:** https://unsplash.com/terms, checked directly. Copyright
  permission is not evidence of permissions for recognizable people, trademarks,
  property or implied endorsements. No releases or endorsement permissions were
  verified. The page's existing captions were not reliable authorship evidence:
  for example, the Why image is by **Avi Theret** on its live photo page, whereas
  the prototype attributed it to Mahmoud Ayad.

## Inventory

`media/` below means `frontend/src/components/public/home-v2/media/`.
CDN identifiers link to the original recorded source, not a replacement.
All **verified / optional** rows use the standard Unsplash licence linked above.

| Placement and local file | Original CDN photo identifier | Individual source page and source title | Licence / visible attribution decision |
| --- | --- | --- | --- |
| Hero and contact — `frontend/public/home-v2-hero.jpg` | [1553284965-83fd3e82fa5a](https://images.unsplash.com/photo-1553284965-83fd3e82fa5a) | [lIeqGEdvex0 — running white horse](https://unsplash.com/photos/lIeqGEdvex0) | Verified / optional; both captions removed. |
| Vets — `media/category-vet.jpg` | [1557374800-8ba4ccd60e9d](https://images.unsplash.com/photo-1557374800-8ba4ccd60e9d) | [MVZlkv_G4zQ — brown horse](https://unsplash.com/photos/MVZlkv_G4zQ) | Verified / optional; removed. |
| Clinics — `media/category-clinic.jpg` | [1563443803769-a5c44bd91e39](https://images.unsplash.com/photo-1563443803769-a5c44bd91e39) | [2s-_S0vAJJI — brown horse close-up photography](https://unsplash.com/photos/2s-_S0vAJJI) | Verified / optional; removed. |
| Hospitals — `media/category-hospital.jpg` | [1629713836806-f0f357363e64](https://images.unsplash.com/photo-1629713836806-f0f357363e64) | [dCr1Ua2-r_4 — brown and black horse on brown field during daytime](https://unsplash.com/photos/dCr1Ua2-r_4) | Verified / optional; removed. |
| Find care — `media/find-care.jpg` | [1685633224332-3b270212cf63](https://images.unsplash.com/photo-1685633224332-3b270212cf63) | [olksAQCS9mk — a brown horse standing next to a wooden fence](https://unsplash.com/photos/olksAQCS9mk) | Verified / optional; removed. |
| Why — `media/why-care.jpg` | [1601726429844-acd8b1385972](https://images.unsplash.com/photo-1601726429844-acd8b1385972) | [RdWyKwb5lbU — grayscale photo of horse head](https://unsplash.com/photos/RdWyKwb5lbU) | Verified / optional; removed. Source author Avi Theret, not the old caption's Mahmoud Ayad. |
| Owner main portrait — `media/owner-portrait.jpg` | [1590839823121-c253bf8d1e7d](https://images.unsplash.com/photo-1590839823121-c253bf8d1e7d) | **Unresolved.** Prototype links only to [Philippe Oursel's profile](https://unsplash.com/@ourselp). An individual matching photo/licence page was not established. | Applicable licence and attribution requirement **unknown**; existing “Owner & horse · Philippe Oursel / Unsplash” credit retained unchanged as a precaution, not confirmed authorship or legal clearance. |
| Owner detail — `media/owner-horse.jpg` | [1604429287879-6bc7a7572048](https://images.unsplash.com/photo-1604429287879-6bc7a7572048) | [1YL46Jd_riU — brown horse head in close up photography](https://unsplash.com/photos/1YL46Jd_riU) | Verified / optional; removed. |
| Veterinary professionals — `media/vet-care.jpg` | [1513966366894-cfe5196c11c0](https://images.unsplash.com/photo-1513966366894-cfe5196c11c0) | [d3p7NVgzGP4 — woman standing beside black and white horse at daytime](https://unsplash.com/photos/d3p7NVgzGP4) | Verified / optional; photographer credit removed, “For the people behind equine care” content retained. Photographer requests credit “if possible”; the page explicitly grants the standard licence. |
| Visiting specialist — `media/visiting-specialist.jpg` | [1589400867230-3491ceee2934](https://images.unsplash.com/photo-1589400867230-3491ceee2934) | [qaF4IhTuZv0 — person riding on white horse on beach during daytime](https://unsplash.com/photos/qaF4IhTuZv0) | Verified / optional; removed. |
| Emergency — `media/emergency-care.jpg` | [1504310977373-186d29f99322](https://images.unsplash.com/photo-1504310977373-186d29f99322) | [OLL7SNhGeZk — photo of brown horse during day time](https://unsplash.com/photos/OLL7SNhGeZk) | Verified / optional; removed. |
| Final CTA — `media/final-horses.jpg` | [1598362042346-70c59713811f](https://images.unsplash.com/photo-1598362042346-70c59713811f) | [-pP8Yy3ARaU — silhouette of horses on field during sunset](https://unsplash.com/photos/-pP8Yy3ARaU) | Verified / optional; removed. |
| Statement detail 1 — `frontend/public/home-v2/statement-detail-1.jpg` | [1610315311683-ef1706f00523](https://images.unsplash.com/photo-1610315311683-ef1706f00523) | [J1z2zcvupHk — brown and white horse eye](https://unsplash.com/photos/J1z2zcvupHk) | Verified / optional; already uncaptioned, unchanged. |
| Statement detail 2 — `frontend/public/home-v2/statement-detail-2.jpg` | [1463748465553-80db1e6ff830](https://images.unsplash.com/photo-1463748465553-80db1e6ff830) | [P6JRr7-FxLw — selective focus photography of two brown horses](https://unsplash.com/photos/P6JRr7-FxLw) | Verified / optional; already uncaptioned, unchanged. |

## Unresolved exception and limits

13 of 14 unique photographs have verified standard-licence pages. **12 visible
credit elements were removed; one portrait credit remains.** Resolve that
portrait with an individual source/licence page or documented permission from
the rights holder before removing its caption. Retaining a credit does not
itself authorize use.

This work does not replace any photograph, purchase a licence, edit a watermark,
change contact behavior, remove map attribution or remove unrelated legal
notices. Figure wrappers and their image-sizing styles remain. Removed credits
were overlays, so no caption row, padding or spacer was needed or added.

## Validation performed

- `cd frontend && npm test -- src/pages/PublicPage.test.tsx --maxWorkers=2`:
  33 tests passed, including all 15 image placements and their unchanged
  alternative text, absence of optional credits, the retained exception and
  existing contact form submissions/interactions.
- `cd frontend && npm run build`: passed (existing Vite configuration and large
  bundle warnings remain).
- Targeted `oxlint` on the changed TSX files: passed.
- `python3 scripts/check-home-photo-credits-browser.py`: passed at 1440px and
  390px; all 15 photos loaded with nonzero dimensions, only the one retained
  credit rendered, no empty captions or horizontal page overflow.
- Desktop provider and mobile owner, emergency and contact captures were
  inspected. Original image frames and non-credit overlays remained intact.
- No image assets changed in Git. No live contact enquiry was sent; submission
  behavior was checked through the existing mocked frontend tests.
