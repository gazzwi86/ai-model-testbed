# Product Launch Meeting -- Project Aurora

**Date:** 2026-03-15  
**Attendees:** Sarah Chen (Product), David Kim (Engineering), Lisa Patel (Marketing), James O'Brien (Design), Rachel Torres (QA)

---

**Sarah Chen:** Thanks everyone for joining. We're four weeks out from the Aurora launch and I want to make sure we're aligned on the remaining work. David, can you start with the engineering update?

**David Kim:** Sure. The core API is feature-complete. We merged the last batch of endpoints on Friday. Performance testing shows response times under 200ms at the p99 level, which exceeds our target of 300ms. The one concern I have is the mobile SDK. We're seeing intermittent crashes on Android 12 devices during image upload. My team is investigating but we don't have a root cause yet.

**Sarah Chen:** That's a blocker for launch. What's your estimate on a fix?

**David Kim:** Realistically, I'd say five business days to diagnose and fix. If it turns out to be a memory issue in the image compression library, we may need to swap to a different library, which adds another two days for integration testing.

**Sarah Chen:** OK. Let's put a decision deadline on this. If we don't have a root cause by end of day Wednesday, we escalate and consider a workaround such as disabling image upload on affected devices for launch. David, please send a status update on Wednesday by 5 PM.

**David Kim:** Will do.

**Lisa Patel:** On the marketing side, the launch blog post is drafted and reviewed by legal. We have the press embargo set for April 12 at 9 AM Eastern. I've confirmed coverage commitments from TechCrunch and The Verge. Social media assets are done. The one open item is the product demo video. James, is the final version ready?

**James O'Brien:** Almost. I'm waiting on updated screenshots from David's team that reflect the new onboarding flow we shipped last week. I should have the final video by Friday.

**Lisa Patel:** Friday works. I need it no later than Monday the 23rd to get it uploaded and captioned in all five languages before the embargo lifts.

**Sarah Chen:** James, please prioritise getting those screenshots to Lisa's team. This is time-sensitive.

**James O'Brien:** Understood. I'll coordinate with David's team tomorrow morning.

**Rachel Torres:** QA update: we've completed 90% of the regression suite. We found three P2 bugs, all filed and assigned. No P0 or P1 issues outstanding apart from the Android crash David mentioned. I'm planning a full end-to-end pass during the week of March 23rd. I'll need a code freeze by March 20th to make that timeline work.

**Sarah Chen:** David, can engineering commit to a code freeze on March 20th?

**David Kim:** Yes, barring the Android fix. If that lands after the 20th, we'll need a targeted exception for that patch only.

**Sarah Chen:** Agreed. We'll grant a freeze exception specifically for the Android image-upload fix, but nothing else after the 20th.

**Rachel Torres:** That works for me.

**Sarah Chen:** Let me summarise the decisions and action items.

**Decisions made:**
1. Launch date remains April 12th unless the Android crash is not resolved by March 25th.
2. Code freeze is March 20th with a single exception for the Android image-upload fix.
3. Press embargo lifts April 12th at 9 AM Eastern.

**Action items:**
- David: Provide Android crash status update by Wednesday March 18th, 5 PM.
- David: Deliver updated onboarding screenshots to James by Thursday March 19th.
- James: Deliver final product demo video to Lisa by Friday March 20th.
- Lisa: Upload and caption demo video in all five languages by Monday March 23rd.
- Rachel: Execute full end-to-end QA pass during week of March 23rd.
- Sarah: Schedule a go/no-go review meeting for March 25th.

**Sarah Chen:** Any questions? No? Great. Next sync is Monday the 23rd. Thanks everyone.
