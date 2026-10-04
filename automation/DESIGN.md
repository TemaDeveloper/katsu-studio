---
name: Katsu Studio
description: An illustrated episode workbench for turning a curious question into a video.
colors:
  yellow: "#ffdf4a"
  yellow-hover: "#f4d032"
  coral: "#ed746b"
  ink: "#242424"
  muted: "#62625e"
  secondary-ink: "#585853"
  canvas: "#fcfcfa"
  white: "#fff"
  line: "#deded8"
  control-border: "#c7c7bf"
  field-border: "#85857d"
  control-hover: "#f1f1ea"
  nav-hover: "#f3f3ed"
  quiet-panel: "#f0f0e9"
  illustration-well: "#f1f1e9"
  episode-well: "#f0f0e8"
  placeholder: "#73736c"
  focus: "#bc8200"
  badge-bg: "#edede7"
  badge-ink: "#55554f"
  completed-bg: "#e7eeda"
  completed-ink: "#3f532b"
  running-bg: "#fff1ad"
  running-ink: "#665313"
  attention-badge-bg: "#ffe5b4"
  attention-badge-ink: "#674511"
  attention-bg: "#fff1c8"
  attention-ink: "#614917"
  error-bg: "#ffe6e2"
  error-ink: "#802f29"
  success-ink: "#456335"
  recipe-bg: "#fff6c9"
  recipe-ink: "#514517"
typography:
  display:
    fontFamily: "'Fredoka Variable',Avenir,sans-serif"
    fontSize: "clamp(32px,4.4vw,52px)"
    fontWeight: 650
    lineHeight: 1.1
    letterSpacing: "-.025em"
  headline:
    fontFamily: "'Fredoka Variable',Avenir,sans-serif"
    fontSize: "25px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-.025em"
  title:
    fontFamily: "'Fredoka Variable',Avenir,sans-serif"
    fontSize: "20px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-.025em"
  body:
    fontFamily: "\"Avenir Next\",Avenir,\"Segoe UI\",sans-serif"
    fontWeight: 450
    lineHeight: 1.5
  label:
    fontFamily: "\"Avenir Next\",Avenir,\"Segoe UI\",sans-serif"
    fontSize: "14px"
    fontWeight: 650
    lineHeight: 1.5
  button-primary:
    fontFamily: "\"Avenir Next\",Avenir,\"Segoe UI\",sans-serif"
    fontWeight: 750
    lineHeight: 1.3
  button-secondary:
    fontFamily: "\"Avenir Next\",Avenir,\"Segoe UI\",sans-serif"
    fontWeight: 650
    lineHeight: 1.25
rounded:
  badge: "4px"
  navigation: "7px"
  control: "8px"
  scene: "10px"
  media: "12px"
  recipe: "14px"
  circle: "50%"
spacing:
  icon-gap: "8px"
  compact-gap: "12px"
  control-inset: "14px"
  action-inset: "20px"
  section-inset: "24px"
  tablet-gutter: "28px"
  grid-gap: "32px"
  desktop-gutter: "48px"
components:
  button-primary:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.ink}"
    typography: "{typography.button-primary}"
    rounded: "{rounded.control}"
    padding: "13px 20px"
  button-primary-hover:
    backgroundColor: "{colors.yellow-hover}"
  button-secondary:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    typography: "{typography.button-secondary}"
    rounded: "{rounded.control}"
    padding: "11px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.control-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "4px 0"
  input:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px 14px"
    width: "100%"
  navigation-item:
    textColor: "{colors.secondary-ink}"
    rounded: "{rounded.navigation}"
    padding: "11px 14px"
  navigation-item-hover:
    backgroundColor: "{colors.nav-hover}"
  navigation-item-active:
    backgroundColor: "{colors.quiet-panel}"
    textColor: "{colors.ink}"
  status:
    backgroundColor: "{colors.badge-bg}"
    textColor: "{colors.badge-ink}"
    rounded: "{rounded.badge}"
    padding: "4px 8px"
  status-completed:
    backgroundColor: "{colors.completed-bg}"
    textColor: "{colors.completed-ink}"
  status-running:
    backgroundColor: "{colors.running-bg}"
    textColor: "{colors.running-ink}"
  status-needs-attention:
    backgroundColor: "{colors.attention-badge-bg}"
    textColor: "{colors.attention-badge-ink}"
  notice-error:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error-ink}"
    rounded: "{rounded.control}"
    padding: "16px 18px"
  notice-attention:
    backgroundColor: "{colors.attention-bg}"
    textColor: "{colors.attention-ink}"
    rounded: "{rounded.scene}"
    padding: "20px 24px"
  notice-paid-attention:
    backgroundColor: "{colors.error-bg}"
    textColor: "{colors.error-ink}"
    rounded: "{rounded.scene}"
    padding: "20px 24px"
  episode-art:
    backgroundColor: "{colors.episode-well}"
    rounded: "{rounded.media}"
  scene-art:
    backgroundColor: "{colors.illustration-well}"
    rounded: "{rounded.scene}"
  recipe:
    backgroundColor: "{colors.recipe-bg}"
    textColor: "{colors.recipe-ink}"
    rounded: "{rounded.recipe}"
    padding: "32px"
  style-preview:
    backgroundColor: "{colors.quiet-panel}"
    rounded: "{rounded.media}"
    padding: "28px"
---

# Design System: Katsu Studio

## Overview

**Creative North Star: "Katsu’s episode workbench"**

The studio feels like a friendly place to make an original illustrated episode. Katsu’s approved white-headed character, black outlines, yellow highlights, and small coral details establish the identity. The interface gives that artwork room to breathe on an almost-white canvas, with charcoal text and expressive rounded headings.

The workbench uses open rows, thin dividers, explicit labels, and native media controls. Yellow makes the next action easy to find; quieter surfaces carry setup, context, and production details. Intermediate work remains inspectable, and the presentation distinguishes measured recordings, targets, estimates, and work that needs attention.

This document records the built interface. Its source is [the final stylesheet](frontend/src/styles.css), [the shared components](frontend/src/components.tsx), and the [page implementations](frontend/src/pages), including the appended font and field-border overrides. The final desktop and mobile evidence in `evidence/final-*.png` confirms the visual system at 1360 × 960 and 390 × 844. The approved brand commitments come from [PRODUCT.md](PRODUCT.md); the sidecar contains standalone component previews and extensions to these tokens.

**Key Characteristics:**

- Original Katsu artwork and expressive Fredoka headings.
- White space, charcoal text, yellow actions, and restrained coral in the artwork.
- Flat, divided work areas with rounded media and controls.
- Visible setup, progress, recovery, and measured production facts.
- Still illustrations, direct cuts, and native video and audio controls.

## Colors

The palette is warm and mostly neutral, with yellow carrying action and illustration highlights. The frontmatter owns exact reusable values.

### Primary

- **Katsu yellow** (`colors.yellow`): primary actions, the headline marker, current production stages, selection, and the empty-state play disc. Its deeper hover partner (`colors.yellow-hover`) confirms interaction.

### Secondary

- **Katsu coral** (`colors.coral`): the source-defined brand accent, visible in the approved avatar and original illustrations. Current interface buttons use yellow; coral does not replace the semantic error colors.

### Neutral

- **Charcoal ink** (`colors.ink`): headings, primary copy, action labels, and runtime overlays.
- **Warm white canvas** (`colors.canvas`) and **white surfaces** (`colors.white`): the application background and fields, player, and media overlays.
- **Muted ink** (`colors.muted`) and **secondary ink** (`colors.secondary-ink`): hints, facts, captions, navigation, and introductory text.
- **Quiet panel** (`colors.quiet-panel`): active navigation and the channel-style aside. Illustration wells provide a neutral pending state behind media.
- **Divider** (`colors.line`): section separation. **Control border** (`colors.control-border`) belongs to buttons; the final, stronger **field border** (`colors.field-border`) belongs to inputs, textareas, selects, and the topic entry container.
- **Focus amber** (`colors.focus`): keyboard focus and active field outlines.

### Semantic states

Completed badges pair pale green with dark green; running badges use pale yellow and olive; attention badges use pale peach and brown. Larger recovery notices use the separate attention background and ink. Error and uncertain paid-request notices pair pale rose with dark red. Successful connection and saved-preference text uses `colors.success-ink`. State words and icons accompany these colors.

**The Action Yellow Rule.** Preserve yellow for the existing action and progress roles; keep the main canvas and media backgrounds light.

**The Visible Field Rule.** Fields use the final field-border token, even though the earlier stylesheet declaration has a lighter border. Keep the focus treatment visible inside the quick-topic entry as well.

## Typography

**Display Font:** self-hosted Fredoka Variable, with Avenir and sans-serif fallbacks. [The entry point](frontend/src/main.tsx) imports `@fontsource-variable/fredoka`; the final evidence confirms that the font loaded on desktop and mobile.

**Body Font:** Avenir Next, Avenir, Segoe UI, sans-serif. Body text and controls inherit this stack. The root uses weight 450 and line-height 1.5; it does not set an explicit body font size. There is no separate named mono role.

**Character:** rounded, lively headings sit above quiet, readable explanatory copy. The final shared heading override uses weight 650 and letter-spacing −0.025em; the brand wordmark uses −0.03em.

### Hierarchy

- **Display** (`typography.display`): page-level headings (32–52px fluid size, line-height 1.1). The creation heading uses 43px and the episode title 37px on desktop. On small screens those become 34px and 30px; the studio introduction uses 35px.
- **Headline** (`typography.headline`): section headings (25px, line-height 1.25). The recipe heading uses 29px with line-height 1.15; the style preview uses 27px.
- **Title** (`typography.title`): smaller headings (20px, line-height 1.3). Episode list titles use 23px, or 30px for a single featured desktop episode; account headings use 18px.
- **Body** (`typography.body`): explanatory copy. General paragraphs have a maximum width of 72ch. Narration has a 74ch container, pre-wrapped paragraphs, 16px text, and line-height 1.9; mobile narration uses 15px.
- **Label** (`typography.label`): persistent field labels (14px, weight 650). Labels sit 18px after preceding content and 8px above their field. Hints and factual metadata usually use 12–14px.
- **Action labels:** primary actions use weight 750 and line-height 1.3; secondary actions use weight 650 and line-height 1.25. Small text actions use 13px, with smaller scene actions on desktop.

**The Two Voices Rule.** Keep Fredoka on the brand wordmark and headings. Keep instructions, narration, field values, status text, and controls on the readable body stack.

## Layout

The shared shell is centered with a maximum width of 1340px and desktop horizontal gutters of 48px. The header is a horizontal brand-and-navigation row with a 102px minimum height and a bottom divider. Main content uses 45px top and 60px bottom padding. Footer content is a simple divided row.

The episode list normally has two equal columns with a 32px gap. At widths of at least 1000px, a lone episode spans the list and places its artwork beside its text in a 1.25:1 split with a 35px gap. The creation and settings pages use a main form and a narrower explanatory aside: `minmax(0,1.4fr) minmax(260px,.8fr)`, with respective desktop gaps of 90px and 80px and maximum widths of 1070px and 1100px. The settings aside is sticky at 30px from the top.

At a maximum width of 1000px, shell gutters become 28px, form-and-aside gaps become 40px, the scene gallery changes from three to two columns, episode actions move below the title, and project facts become two columns. The channel-name label disappears. The scene gallery uses a 32px row gap and 23px column gap.

At a maximum width of 650px, shell gutters become 20px and main padding becomes 28px top and 40px bottom. Navigation wraps below the brand and keeps all three links visible. The quick-topic field and action stack; episode lists, scene galleries, and form-and-aside layouts become one column. Paired numerical inputs remain a two-column row with a 13px gap. Production stages become a two-column list. Tabs can scroll horizontally, account-key save actions expand to full width, and the settings aside becomes static. The sticky preference save area places its full-width action above its status message.

**The Artwork First Rule.** Keep illustration and video wells at 16:9. Episode thumbnails fill their well with `object-fit: cover`; scene illustrations use `object-fit: contain` so the full drawing remains visible. Avatar images are contained rather than cropped.

## Elevation & Depth

The current interface has no CSS box shadows. Depth comes from the almost-white canvas, white fields, quiet gray panels, warm recipe and recovery backgrounds, and thin one-pixel dividers. Media corners clip their content; a runtime chip and scene-number label sit directly over the artwork. The sticky settings aside and save row use positioning rather than a raised shadow.

**The Flat Workbench Rule.** Preserve the existing flat treatment for rows, controls, and work areas. Use the established tonal surfaces and dividers to distinguish context and state.

## Shapes

Controls use gently rounded corners (`rounded.control`, 8px). Navigation uses 7px corners. Artwork and video containers use 12px corners, scene images and recovery notices 10px, and the yellow recipe aside 14px. Small badges and over-image labels use 4px corners. Stage markers and play discs are circular.

Borders remain straight and thin; the organic character belongs to the illustrations and Fredoka letterforms. A yellow marker sits behind the lower part of the studio headline. It is a static highlight, with its vertical coverage adjusted on mobile.

## Components

### Buttons

Primary actions are solid yellow with charcoal text, matching yellow borders, 8px corners, and 13px × 20px padding. Hover changes both background and border to the yellow-hover token. Secondary buttons use white, the control-border token, and 11px × 16px padding; hover adds the quiet control-hover background. Text actions remove the border and background and underline on hover.

Disabled buttons use opacity 0.5 and a not-allowed cursor. Keyboard focus is a 3px amber outline with a 4px offset. Buttons and links use touch-action manipulation. Mobile quick-topic and settings-save actions expand across their container.

### Inputs / Fields

Inputs, textareas, and native selects use white backgrounds, charcoal text, the final field-border token, 8px corners, and 12px × 14px padding. Focus uses a 2px amber outline with a 1px offset. Placeholders use their own muted token at full opacity. Textareas resize vertically; the topic entry uses 22px text and a 145px minimum height. Persistent labels and nearby hints explain the field; numerical units appear at the right of applicable inputs.

The quick-topic container is a bordered 12px-rounded row with its action inside. Its input removes the resting inner border but restores a visible outline for keyboard focus. Secret-key entries use password inputs and a separate save action. Advanced spending and model options use native disclosure elements.

New-video length and its settings default use a single labeled minutes field, no wider than 260px. There is no illustration-count control. Its hint explains that the completed script determines the images and exact wording pairs. Before the scene plan exists, project summaries say the count follows the script; once planned, they display the actual total.

### Navigation and episode tabs

Main navigation combines line icons and text. Links use 14px body text, weight 650, 11px × 14px padding, and 7px corners. Active navigation uses the quiet-panel background and charcoal text; hover uses the nav-hover background. On mobile, all three links stay in a second header row with 12px text.

Episode tabs sit on a divider and use a 3px charcoal underline for the selected state. Their labels stay on one line; mobile tabs can scroll. The implementation uses tab and tabpanel roles, an associated selected state, roving focus, and Arrow Left/Right, Home, and End keyboard behavior. Keep those behaviors when extending the tab strip.

### Status badges and notices

Status badges use 11px body text, weight 700, 4px × 8px padding, and 4px corners. Their displayed words are “Waiting,” “In production,” “Needs attention,” “Stopped,” and “Ready to watch.” Colors reinforce these labels.

Errors use a rose notice with an alert role and icon. Recovery messages use a warm attention panel and an actionable Settings link. An uncertain paid request uses the rose panel with an explicit acknowledgement checkbox before another attempt becomes available. Loading text carries a status role. Saved-preference feedback also uses a status role.

### Episode rows and scene gallery

Episode entries combine a 16:9 thumbnail, a circular play mark, a measured runtime chip when available, status, date, title, and an “Open episode” or “Follow production” link. The row has a bottom divider rather than an enclosing card border. Hover makes the play disc yellow. Missing artwork uses an explicit pending message.

Each scene pairs its contained illustration with a scene-number overlay, exact voiceover, and “Edit scene” and “New image” text actions. Editing opens labeled wording and visual-description fields with Save and Cancel actions. The accompanying hint explains that changing words creates new narration and changing the visual updates the image. Scene actions are disabled while production is active. Gallery images load lazily and use their visual descriptions as alt text.

### Production, player, and facts

Production uses eight labeled stages: Research, Narration, Scene plan, Images, Voice, Timing, Export, and Thumbnail. Numbered circular markers become checks when completed; the current stage is yellow. Image production shows completed and total illustration counts. The desktop stage grid has eight columns, four below 1000px and two below 650px. A completed historical import uses its own preservation notice instead of implying that a new generation pipeline ran.

The **Thumbnail** episode tab follows Images and precedes Sources. Its desktop panel pairs a large 16:9 preview with a short headline and download/regeneration actions. At 650px it stacks into one column. It shares the existing rounded preview, Fredoka headings, charcoal text and yellow primary action. The thumbnail also supplies the episode-list cover and video poster when available. A stopped thumbnail still leaves the saved video downloadable and exposes Continue production. The first episode identifies its Codex-created artwork separately from future connected-account generation.

The player uses native video controls with metadata preload and a 16:9 canvas. A caption gives format facts and links to export checks. Narration uses native audio controls when the recording exists. Facts distinguish target length, recorded length, committed estimates and limit, and voice. Download actions expose the video, script data, timing report, narration text when available, and image package with wording.

**The Measured Facts Rule.** Keep recorded runtime separate from the target, and committed estimates separate from provider billing. Use real stage names and asset counts for progress.

### Brand and context panels

Use the approved avatar in the header, studio introduction, waiting-video state, and channel-style preview. Preserve its expressive oversized white head, curl, black stick limbs, uneven black outlines, and yellow/coral detail. The yellow recipe aside explains the existing production flow; the quiet style aside keeps the saved visual identity close to settings. Original scene illustrations are the main content, rather than interchangeable decorative stock imagery.

### Motion

The only authored animation is the loading spinner: one full rotation every 1.1 seconds, linear and infinite. Reduced-motion preference removes that animation and forces automatic scroll behavior. Current button, navigation, and tab state changes are immediate; the stylesheet declares no general transition token. Episode illustrations remain still and exports use direct cuts.

## Do's and Don'ts

### Do:

- **Do** reuse the approved avatar and original illustrated assets with their existing aspect ratio and containment rules.
- **Do** apply the final Fredoka heading and field-border overrides, alongside the readable body stack.
- **Do** keep persistent labels, visible keyboard focus, text-based states, and the existing tab keyboard behavior.
- **Do** let content reflow at the observed 1000px and 650px breakpoints, retaining visible navigation and usable save actions.
- **Do** preserve exact scene wording near its illustration and explain the consequences of edits.
- **Do** distinguish actual recorded length, targets, spending estimates, and uncertain paid-request recovery.

### Don't:

- **Don't** replace Katsu’s approved character with generic imagery or crop scene illustrations to fill their wells.
- **Don't** erase field outlines or communicate status only through color.
- **Don't** present an eight-minute target or spending estimate as a measured result or confirmed bill.
- **Don't** invent progress percentages, completion times, or a research record for a historical import.
- **Don't** animate illustrations, add camera movement, or introduce audio speed changes to force a runtime.
- **Don't** expose API keys in ordinary text fields, browser persistence, or exported artifacts.
