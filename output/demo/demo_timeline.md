# Reaction demo: what the system does next

Every message below went to the test inbox (`output/outbox/demo/`), never to a clinic.

## Clicks the sample, then takes the call
**Leonid Kozer Medical** · Tier A · score 77 · final status **sales_ready**

> SALES-READY on Day 3: explicit interest (live call). Evidence: link click (Day 2, Leonid Kozer); call interested (Day 3, practice manager). Fit: Tier A (77/100): independent cardiology practice; 1 cardiologist(s), 3 site(s); 25% limited-English households in 11230, mostly Russian; decision-maker named in NPPES (Owner)

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Leonid Kozer Medical -> Leonid Kozer Medical |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Leonid Kozer |
| 1 | touch | EMAIL 'Russian + English home blood-pressure sheet for Dr. Kozer's patients' to Leonid Kozer (decision-maker (Owner)) -> test inbox |
| 1 | event | EMAIL OPEN by Leonid Kozer |
| 2 | event | LINK CLICK by Leonid Kozer |
| 2 | decision | They looked at the sample. Answer while it is fresh and switch to a person. |
| 2 | touch | EMAIL 'Re: Russian + English home blood-pressure sheet for Dr. Kozer's patients' to Leonid Kozer (engaged contact) -> test inbox |
| 2 | action | Call already queued for Day 3; kept it. |
| 2 | action | Cancelled email_2_bump. |
| 3 | touch | CALL TASK: Call script: front desk to practice manager -> Front desk (718) 375-2825 |
| 3 | event | CALL INTERESTED by practice manager |
| 3 | decision | Live interest on the phone. |
| 3 | action | Stopped automation (5 remaining steps cancelled). |
| 3 | surface | SALES-READY -> AE alerted. Reason: explicit interest (live call). |

## Opens three times, never clicks, then scans the mailed QR
**Sorin Medical** · Tier A · score 86 · final status **sales_ready**

> SALES-READY on Day 9: engagement 36 >= 35 on a Tier A account (linkedin accept, 3x email open, call gatekeeper, qr scan). Evidence: qr scan (Day 9, Maria Lopez). Fit: Tier A (86/100): independent multispecialty group; 6 cardiologist(s), 9 site(s); 45% limited-English households in 11220, mostly Spanish and Chinese; decision-maker named in NPPES (Owner); champion: Dr. Omar

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Sorin Medical -> Sorin Medical |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Wally Omar |
| -3 | event | LINKEDIN ACCEPT by Dr. Wally Omar |
| -3 | decision | Connection accepted, so the Day 9 LinkedIn message is allowed. |
| -3 | action | LinkedIn message step unlocked. |
| 1 | touch | EMAIL 'Spanish/Chinese + English diabetes-and-heart sheet for Sorin Medical patients' to Joseph Puma (decision-maker (Owner)) -> test inbox |
| 1 | event | EMAIL OPEN by Joseph Puma |
| 1 | event | EMAIL OPEN by Joseph Puma |
| 1 | event | EMAIL OPEN by Joseph Puma |
| 1 | decision | 3+ opens in 48h. Opens alone are unreliable, so the move is a human call, not another email. |
| 1 | action | Pulled call_1 forward from Day 3 to Day 2. |
| 2 | touch | EMAIL 'Would you mark this up? (diabetes-and-heart, in Spanish and Chinese)' to Dr. Wally Omar (clinical champion) -> test inbox |
| 2 | touch | CALL TASK: Call script: front desk to practice manager -> Front desk (718) 266-0900 |
| 2 | event | CALL GATEKEEPER by front desk {"name": "Maria Lopez", "role": "office manager"} |
| 2 | decision | Got a name from the front desk. Add them as a contact. |
| 2 | action | Added contact Maria Lopez (office manager). |
| 5 | touch | EMAIL 'Re: Spanish/Chinese + English diabetes-and-heart sheet for Sorin Medical patients' to Joseph Puma (decision-maker (Owner)) -> test inbox |
| 7 | decision | Silence since Day 5. Next touch switches to direct mail (mail_1). |
| 7 | touch | MAIL PACKET (Lob): Direct mail packet (printed, Lob API) -> Joseph Puma |
| 9 | decision | Silence since Day 7. Next touch switches to linkedin (li_message). |
| 9 | touch | LINKEDIN DRAFT: LinkedIn message (only after they accept) -> Wally Omar |
| 9 | event | QR SCAN by Maria Lopez |
| 9 | decision | The printed packet reached the office and someone acted on it. |
| 9 | touch | EMAIL 'Glad the printed copies arrived' to Maria Lopez (engaged contact) -> test inbox |
| 9 | surface | SALES-READY -> AE alerted. Reason: engagement 36 >= 35 on a Tier A account (linkedin accept, 3x email open, call gatekeeper, qr scan). |
| 10 | event | LINK CLICK by Maria Lopez |
| 10 | decision | Account is already with the AE: activity forwarded to them, automation stays off. |

## Total silence: channel escalation, then nurture
**Dr. Jeffrey Ma (solo cardiology)** · Tier A · score 76 · final status **nurture**

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Dr. Jeffrey Ma (solo cardiology) -> Dr. Jeffrey Ma (solo cardiology) |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Jeffrey Ma |
| 1 | touch | EMAIL 'Chinese + English home blood-pressure sheet for Dr. Ma's patients' to Jeffrey Ma (decision-maker (Physician owner (inferred))) -> test inbox |
| 3 | decision | Silence since Day 1. Next touch switches to phone (call_1). |
| 3 | touch | CALL TASK: Call script: front desk to practice manager -> Front desk (718) 762-8615 |
| 5 | decision | Silence since Day 3. Next touch switches to email (email_2_bump). |
| 5 | touch | EMAIL 'Re: Chinese + English home blood-pressure sheet for Dr. Ma's patients' to Jeffrey Ma (decision-maker (Physician owner (inferred))) -> test inbox |
| 7 | decision | Silence since Day 5. Next touch switches to direct mail (mail_1). |
| 7 | touch | MAIL PACKET (Lob): Direct mail packet (printed, Lob API) -> Jeffrey Ma |
| 9 | decision | Skipped li_message: LinkedIn request not accepted, no message. |
| 12 | decision | Silence since Day 7. Next touch switches to email (email_3_proof). |
| 12 | touch | EMAIL 'What the full version looks like for your practice' to Jeffrey Ma (decision-maker (Physician owner (inferred))) -> test inbox |
| 15 | decision | Silence since Day 12. Next touch switches to phone (call_2). |
| 15 | touch | CALL TASK: Call script: follow-up on the mailed packet -> Front desk (718) 762-8615 |
| 21 | decision | Silence since Day 15. Next touch switches to email (email_4_close). |
| 21 | touch | EMAIL 'Closing the loop' to Jeffrey Ma (decision-maker (Physician owner (inferred))) -> test inbox |
| 21 | decision | Sequence finished with no reply. Moved to nurture (monthly free template, retargeting ads). Re-enters on Day 111 or sooner on a trigger (new site, new clinician, job post). |

## Objects ('we already have handouts'), then says yes
**Khait Medical Care** · Tier A · score 84 · final status **sales_ready**

> SALES-READY on Day 14: explicit interest (Ok, send it over and let's find 15 minutes next week.). Evidence: reply has materials (Day 2, Eugene Khait); reply positive (Day 14, Eugene Khait). Fit: Tier A (84/100): independent cardiology practice; 2 cardiologist(s), 2 site(s); 38% limited-English households in 11224, mostly Russian; decision-maker named in NPPES (M.D.); champion: Dr. Hai

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Khait Medical Care -> Khait Medical Care |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Ofek Hai |
| 1 | touch | EMAIL 'Russian + English home blood-pressure sheet for Dr. Khait's patients' to Eugene Khait (decision-maker (M.D.)) -> test inbox |
| 2 | decision | Silence since Day 1. Next touch switches to email (email_champion). |
| 2 | touch | EMAIL 'Would you mark this up? (home blood-pressure, in Russian)' to Dr. Ofek Hai (clinical champion) -> test inbox |
| 2 | event | REPLY from Eugene Khait: "Thanks, but we already give patients the AHA handouts." -> classified reply_has_materials |
| 2 | decision | Objection, not a no. Answer it once, then give space. |
| 2 | touch | EMAIL 'Re: Russian + English home blood-pressure sheet for Dr. Khait's patients' to Eugene Khait (engaged contact) -> test inbox |
| 2 | action | Paused 5 days: remaining steps shifted (next now Day 8). |
| 8 | touch | CALL TASK: Call script: front desk to practice manager -> Front desk (718) 616-2507 |
| 10 | decision | Silence since Day 8. Next touch switches to email (email_2_bump). |
| 10 | touch | EMAIL 'Re: Russian + English home blood-pressure sheet for Dr. Khait's patients' to Eugene Khait (decision-maker (M.D.)) -> test inbox |
| 12 | decision | Silence since Day 10. Next touch switches to direct mail (mail_1). |
| 12 | touch | MAIL PACKET (Lob): Direct mail packet (printed, Lob API) -> Eugene Khait |
| 14 | decision | Skipped li_message: LinkedIn request not accepted, no message. |
| 14 | event | REPLY from Eugene Khait: "Ok, send it over and let's find 15 minutes next week." -> classified reply_positive |
| 14 | decision | Explicit interest. Stop automation and hand to a human within one business day. |
| 14 | action | Stopped automation (3 remaining steps cancelled). |
| 14 | surface | SALES-READY -> AE alerted. Reason: explicit interest (Ok, send it over and let's find 15 minutes next week.). |

## Refers us to the office manager, who engages
**Song Heart and Vascular** · Tier A · score 75 · final status **sales_ready**

> SALES-READY on Day 2: 2 people engaged: Elena Ruiz, Jason Song. Evidence: reply referral (Day 1, Jason Song); link click (Day 2, Elena Ruiz). Fit: Tier A (75/100): independent cardiology practice; 1 cardiologist(s), 2 site(s); 23% limited-English households in 11358, mostly Korean, Chinese and Spanish; decision-maker named in NPPES (Medical Director)

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Song Heart and Vascular -> Song Heart and Vascular |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Jason Song |
| 1 | touch | EMAIL 'Korean, Chinese/Spanish + English PAD walking-plan sheet for Dr. Song's patients' to Jason Song (decision-maker (Medical Director)) -> test inbox |
| 1 | event | REPLY from Jason Song: "Please speak with our office manager Elena Ruiz, she handles this." -> classified reply_referral |
| 1 | decision | Pointed to the right person. Thread them in with the referrer's name; that borrowed trust is the strongest asset we have. |
| 1 | action | Added contact Elena Ruiz (office manager). |
| 1 | touch | EMAIL 'Dr. Song suggested I reach out' to Elena Ruiz (referred contact) -> test inbox |
| 2 | event | LINK CLICK by Elena Ruiz |
| 2 | decision | They looked at the sample. Answer while it is fresh and switch to a person. |
| 2 | touch | EMAIL 'Re: Korean, Chinese/Spanish + English PAD walking-plan sheet for Dr. Song's patients' to Elena Ruiz (engaged contact) -> test inbox |
| 2 | action | Call already queued for Day 3; kept it. |
| 2 | action | Cancelled email_2_bump. |
| 2 | surface | SALES-READY -> AE alerted. Reason: 2 people engaged: Elena Ruiz, Jason Song. |

## 'Not now, check back after the holidays'
**Dr. Subhash Malhotra (solo cardiology)** · Tier A · score 74 · final status **snoozed**

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Dr. Subhash Malhotra (solo cardiology) -> Dr. Subhash Malhotra (solo cardiology) |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Subhash Malhotra |
| 1 | touch | EMAIL 'Spanish/Chinese + English home blood-pressure sheet for Dr. Malhotra's patients' to Subhash Malhotra (decision-maker (Physician owner (inferred))) -> test inbox |
| 2 | event | REPLY from Subhash Malhotra: "Too busy right now. Check back after the holidays." -> classified reply_not_now |
| 2 | decision | Timing objection. Respect it, come back when they said. |
| 2 | touch | EMAIL 'Re: Spanish/Chinese + English home blood-pressure sheet for Dr. Malhotra's patients' to Subhash Malhotra (engaged contact) -> test inbox |
| 2 | action | Stopped automation (7 remaining steps cancelled). |
| 2 | action | Snoozed. Re-enters with a fresh angle on Day 62. |

## Auto-reply out of office, then the champion's email bounces
**Tien Cardiology Associate** · Tier A · score 73 · final status **sales_ready**

> SALES-READY on Day 17: engagement 35 >= 35 on a Tier A account (qr scan, link click). Evidence: qr scan (Day 16, Hung-Sam Lee); link click (Day 17, Hung-Sam Lee). Fit: Tier A (73/100): independent cardiology practice; 1 cardiologist(s), 1 site(s); 40% limited-English households in 11354, mostly Chinese and Spanish; decision-maker named in NPPES (Physician)

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Tien Cardiology Associate -> Tien Cardiology Associate |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Hung-Sam Lee |
| 1 | touch | EMAIL 'Chinese/Spanish + English home blood-pressure sheet for Tien Cardiology Associate patients' to Hung-Sam Lee (decision-maker (Physician)) -> test inbox |
| 1 | event | REPLY from Hung-Sam Lee: "I am out of the office until December 10 with limited access to email." -> classified out_of_office |
| 1 | decision | Nobody is reading. Move the rest of the sequence to after their return date. |
| 1 | action | Out of office until Day 9: shifted 7 steps by 9 days. |
| 11 | event | BOUNCE by Hung-Sam Lee |
| 11 | decision | Email is dead. Switch to phone and mail, and re-enrich the contact. |
| 11 | action | Email marked invalid; contact queued for re-enrichment. |
| 11 | action | Call already queued for Day 12; kept it. |
| 12 | decision | Silence since Day 1. Next touch switches to phone (call_1). |
| 12 | touch | CALL TASK: Call script: front desk to practice manager -> Front desk (718) 762-1888 |
| 14 | decision | Skipped email_2_bump: email bounced; phone and mail carry the sequence. |
| 16 | decision | Silence since Day 12. Next touch switches to direct mail (mail_1). |
| 16 | touch | MAIL PACKET (Lob): Direct mail packet (printed, Lob API) -> Hung-Sam Lee |
| 16 | event | QR SCAN by Hung-Sam Lee |
| 16 | decision | The printed packet reached the office and someone acted on it. |
| 16 | touch | EMAIL 'Glad the printed copies arrived' to Hung-Sam Lee (engaged contact) -> test inbox |
| 17 | event | LINK CLICK by Hung-Sam Lee |
| 17 | decision | They looked at the sample. Answer while it is fresh and switch to a person. |
| 17 | touch | EMAIL 'Re: Chinese/Spanish + English home blood-pressure sheet for Tien Cardiology Associate patients' to Hung-Sam Lee (engaged contact) -> test inbox |
| 17 | action | Added a human call for Day 18. |
| 17 | surface | SALES-READY -> AE alerted. Reason: engagement 35 >= 35 on a Tier A account (qr scan, link click). |

## Asks to be removed
**Amnon Beniaminovitz MD** · Tier A · score 71 · final status **suppressed**

| Day | Kind | What happened / decision |
|---:|---|---|
| -7 | touch | AD AUDIENCE SYNC: Audience sync: Amnon Beniaminovitz MD -> Amnon Beniaminovitz MD |
| -5 | touch | LINKEDIN DRAFT: LinkedIn connection note -> Amnon Beniaminovitz |
| 1 | touch | EMAIL 'Chinese + English home blood-pressure sheet for Dr. Beniaminovitz's patients' to Amnon Beniaminovitz (decision-maker (Owner)) -> test inbox |
| 1 | event | REPLY from Amnon Beniaminovitz: "Please remove me from your list." -> classified reply_unsubscribe |
| 1 | decision | No means no, across every channel. |
| 1 | action | Stopped automation (7 remaining steps cancelled). |
| 1 | action | Suppressed on every channel (email, phone, mail, LinkedIn, ads). |

## Cohort run: all 75 with seeded random behavior

Status counts: {'sales_ready': 11, 'nurture': 62, 'snoozed': 1, 'suppressed': 1}. Sales-ready: 11 of 75 (15%).

## Funnel verdict

Working every independent NYC cardiology practice once yields about 27 first conversations; adding hospital-system sites, a 90-day recycle and referrals brings the whole market to about 56. That is 0.7 months of a 75/month target. Hitting 75 every month needs about 789 fresh accounts a month at the blended rate, so the same engine has to widen: cardiometabolic-adjacent specialties in NYC (endocrinology, nephrology), then metro cardiology (Long Island, Westchester, North Jersey).
