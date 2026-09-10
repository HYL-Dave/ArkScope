# SDD ledger - plan: docs/superpowers/plans/2026-09-10-sec-retention-inventory-and-helper-cleanup.md

## Current Status

| Task | Status | Evidence / Owner |
| --- | --- | --- |
| 1 | Complete for authorized statistics; independent trace/artifact review ACCEPT | Renewedauthorized invocation exit0 in0.257s, query45ms. Mainmetadataunchanged,32FKgroups0orphans,oldweb7tablesabsent. No backup/disposal. |
| 2 | Complete | `5d41f570` plus test-only `58e1929b`; independent spec/quality review and M1 re-review clean; parent43P. |
| 3 | Complete, all scoped reviews passed | `0c5896a5`,962 scoped passed; facade `e61accaf`,293P/10 full files, one added absence owner/no ID loss. P2 re-review PASS/PASS, six retained test ASTs verified. |
| 4 | Complete for this source checkpoint; final review and docs re-review PASS | Full0c5896a5:7971P/12S. Laterfix293P. Final7984 IDs all covered by labelled runs, combined7972P/12S (not a second whole-suite run). Front1692P/typecheck/build passed. Census exit2. |

No logical production write, backup, provider call, App restart, merge or push.
The renewed read used explicitly authorized SQLite WAL/SHM coordination only.
Current translation/history/confirmation and stored evidence remain protected.
Task1's initial unavailable result was not empty data or approval to delete it;
the renewed measured manifest likewise does not authorize disposal.

## Chronological Record

The detailed notes below retain intermediate failures and rulings. A proposed
whole-file formatting patch was rejected because delete/add targeted the same
file; no ledger content was lost. The pre-format copy is progress-checkpoint.txt.

Base6ba563d9; plan8c8ac738. User authorized the exact two-store statistics-only read and continued approved source cleanup, not writes/integration/provider calls.

| Task / overlap | Preflight result |
| --- | --- |
| 1 | Query must not use broad disposal preview or snapshot; synthetic private-column denial and missing-table distinction before actual read. |
| 2 | Exact journal bytes unchanged; shared codec does not imply deleting historic journal records. |
| 3 | Five HTTP entries only; same-name tool methods remain live and must be preserved. |
| 4 | Count changes must match removed behavior; no production-count claims before Task1. |
| 1 / 2 / 3 | Source changes do not touch production; recorded query source revision is independent of later helper/route edits. |
| 2 / 3 | No shared product write set; final integration verifies history/confirmation behavior. |
| 1-3 / 4 | Separate evidence for measured retention versus source cleanup; no automatic disposal inference. |

Task1: in progress, controller owns immediate query/privacy gate.
Task2: in progress, Heisenberg01a08bee-8503-7f11-a766-834aa9fc51a9; base8c8ac738.
Task3: pending.
Task4: pending.

The previous plan's ignored workspace was removed after archival. Its exact offline test runner will be copied from archived evidence into this plan's own scratch location. No other plan workspace is used. The skill helper was not executable; running the unchanged script with bash succeeded, no chmod needed.

Task1 privacy gate: synthetic RED12failed (missing inspector), initialGREEN12passed in0.50s. Before review remove generic `key` column access (only exact profile_settings key predicates need it), and move per-store finished timestamp after FK reads. Raman01a08bed-d567-79c0-b9f0-dc8886130e5d reviews query/fixtures before production execution, no production access delegated.

Ruling: Task3 removes the translation orchestrator and exclusive store methods when removing their last runtime route. Full src/apps reference search shows only that route imports security_lifecycle_translation; all other imports are its tests. Keeping it would introduce another tests-only obsolete facade. Cost if wrong: restore a missed actual consumer; active card/content translation remains under separate unchanged owners and full regression. Translation schema/rows are not dropped. Additional collateral is explicitly named in the plan before Task3 dispatch.

Task-brief helper invokes its non-executable sibling and exited126 even under bash. Instead of chmod on plugin files, copied the exact Task2 requirements/constraints into this plan's manual brief with apply_patch. No product behavior affected.

Task1 review raised two real pre-read gaps. Ordinary mixed-affinity equality counted1 match for TEXT'01'/INTEGER1 while parent-affinity comparison and PRAGMA foreign_key_check prove0matches/1orphan. Fix uses p.parent=+c.child and three affinity/collation tests. SQLite mode=ro does not prove zero WAL coordination writes; existing /usr/bin/bwrap succeeds with --ro-bind / / --unshare-net. A synthetic live-WAL writer preservesuncheckpointedrow; read-only-view child seesit, deniedappendandunchangedmain/WAL/SHMbytesprovefilesystemboundary. Production invocation will expose only this plan's output scratch writable, all production paths readonly. No new app/runtime dependency or global setting installed. Result field narrowedlogical_database_writesFalse, filesystemcallerboundaryexplicit. Added source-verified exactold scheduler/job counts, removedspeculativeconfirmationstable and measuredtranslationdigestcomposite. ReviewRED3F16P, GREEN19P; scoped Raman rereview pending beforeactualread.

Source clarification for Task3: store.list_evidence has a direct SQL translation JOIN even after removing three exclusively-used named translation methods. Keep it and its case-tool provenance/no-translated-text owner; seed fixturehistoricalrow directly instead of callingdeletedtranslator. Plan/brief updated beforedispatch. No extra productremoval.

Task1 read-only gate: Raman scoped re-review19P, no remaining blocker under caller bwrap boundary, report inventory-rereview.md. Reviewed query SHA matched. One authorized production attempt under root-readonly bwrap failed with OperationalError at ATTACH market before BEGIN/metadata/aggregate queries, exit1. No result file. Exact-file stat only afterfailure: profile WAL/SHM absent; market WAL empty/SHM present. This is consistent with readonly WAL initialization but doesnot identify the exact production cause. No retry/fallback/copy/checkpoint. production-attempt.json records unavailable, not zero. Task1 is incomplete for measuredcounts; continue independent source tasks. Production disposal remains blocked pending usable authorized snapshot/read.

Task2 implementation5d41f570: 349P, 41 added/0removed. Parent read scoped core diff; fresh taskreview dispatched, report task2-review.md. Worker Heisenberg closed after report. Raman closed after inventoryre-review.

Task2 review Bernoulli01a08bfd-7057-7162-a937-f00b73fbb94b: specPASS/qualityAPPROVED with minorM1, directimportpresence doesnotprevent legacyhelperforwarders returning. Ruling: fix M1 now with narrownegativeowner tests and two mutationtypes; do notpark same no-ownerpattern userhas repeatedly rejected. Resumed Heisenberg for fixround1, testonlycommit beforeTask3.

Task1 postfailure syntheticcheck20P proves a closed WAL/no-sidecar fixture failsunderreadonlyrootwithoutcreatingfiles; existingliveWALfixture stillreads latestrowunchanged. Doesnotclaim definitiveproductioncause. Asked user narrowlywhether SQLiteWAL/SHM coordination creation/updates permitted while logicalqueriesreadonly; no secondattempt untilreply. Productionqueryunchanged; evidencearchivedunder sec-retention-helper-cleanup.

Frontend check at5d41f570: whole suite1692P/119files, no failures/errors/skips, same112stderr-bearingcases expectedReactactwarnings. tsc--noEmit exit0. No apps/ sourcefiles changed inthisplan; finalintegration willverifyunchangedfrontendinputs. Buildstartedseparately, outcomeawaitingcapture.

Frontendbuildexit0, JS1155.31kB existingchunkwarning. Artifactcomparison initiallyselected task4-final-frontend.xml and found9labels beforefixturewrapping; correct completed artifact task4-verified-frontend.xml has exact1692nodeidentities andidentical112stderrcases. Noquietnormalization/nodeignore. frontend-checks.json recordsboth.

Task2 M1fix58e1929b:27testlines only, product unchanged. Parent readfullfixdiff, scopedBernoullire-reviewdispatched. Exactactualmutantartifacts task2-state/m1/artifacts; priorparentmessage guessedm1-artifacts spelling, correctfilesystemlistprovidedbyinspection. Task2implementationreturnedslowlyfromclosedagent; afterbounded300s waitnoresult, statecheckedandcommitobservedratherthanredispatchingcompletedwork.

Task2M1reportreceived, parentfresh43P. Sourcecopiesmutatedonlyinignoredfixtures, oldtests41Pmissbothaliases/importuse,new43nodes kill3/3/4/4respectivemutants; actualsrcunchanged. Originalworkerclosedaftercompletedreport, nooverlappingwriters. Ruling: proceedTask3 afteroriginalTask2specPASS/qualityAPPROVED andM1testonlyfix/parentverification; M1scopedre-reviewhas no productdependencyandremainsrequiredbyfinalgate. This avoids holding unrelatedroutebaselinebehindreportlatency; do notclaimM1reviewdoneyet.

Task3implementerdispatchedon58e1929b; exactbrief/task3-report.md. Parentownsdocsanddataapprovalonlywhileworkerownsroute/translation/tests.

Task 2: complete. M1scopedre-reviewFIXED/specPASS/qualityAPPROVED,noopenfindings. Report task2-m1-review.md archived. ReviewerBernoulliclosed. Task3Kant01a08c10-33f9-7872-b34f-54ad51e22f9c active; sequentialimplementationownershipconfirmed.

Task3 `0c5896a5`: originalactualApp221, final216, exactlyfive removed/noaddedroutes. Scoped baseline975P; RED5F/1P; intermediate6P/2F(oldcount/surfaceowners); green962P; restoreoldconfirmationregistrationmutant1F; restored962P. Six preserved-owner renames,18obsolete-onlytestremovals,fivenewabsenceowners. Workerclosed aftercompletedreport. Fresh scopedreview dispatched. Parentwholebackend startedonfrozencode with collectionmanifest hook, session46865. Census started separately; no runtimeeditsduringverification.

Census at0c5896a5 exited2 as intended:1097read/4324candidate rows/3387uncertainties. Original baseline:new197unique candidates(88CSS/100i18n/9SQL),264uncertainty IDs,32deliberate removals,no dependency/untracked drift. Comparedpreviousphase:fiveHTTPcandidatesgone;9translationtable/columncandidatesadded. Actual list_evidence SQLreader remains. Source-only in-memory reproduction shows scanner union schema lackssecurity_lifecycle_evidence, failing EXPLAIN beforecapturingJOINreader. Keep rawreport/knownlimitation andcurrentreader; no scannerrewrite-to-green or dataDROP. census-interpretation.json recordsexactgap.

Additional Task3 namedrisk sent toMeitnerreviewer01a08c21-7951-74b1-9ddb-b880d50f52f8: removedconfirmationHTTPleaves TickerIdentityService.get_review_confirmation wrapper referencedonlybytests. Underlying security_lifecycle_review._result andconfirmation_for havecurrentcallers. Evaluatefacade separatelyfromrealreceiptreader; no runtimechangeswhileparentfullsuiteruns.

Task3 initialscopedreviewPASS/PASS,nofindings, archivedtask3-review.md. Separatefacadefollow-uprequestedbecauseinitialreportdoesnotexplicitlyresolvenewlytest-only4linewrapper. Ruling: removeunusedget_review_confirmation aftercurrentfullrun,moveexistingtestcallstoactual_resultownerandaddabsenceguard; keep_result/confirmation_fordatareadsunchanged. Sameexclusive-last-callerpolicyastranslator. Costifwrong: restore4linefacadeforunknownconsumer; no data/HTTP/codecchange. Runtime remains0c5896a5untilfullsuitestops.

Whole backend at0c5896a5 finished:7971 passed/12 skipped,7983 unique collected/executed IDs,742.764s. Accounting script verifies exact JUnit-to-node correspondence:baseline7953,54 added/24 removed. Frontend1692 IDs and112stderr-bearing cases exactly match previous final baseline. Evidence verification-summary.json. Session46865 was already completed on context recovery; no duplicate run. Meitner's separate facade review confirms P2; original review remains unchanged. Kant resumed with task3-facade-brief.md after the frozen run completed; parent owns docs/evidence, no concurrent product edits.

Task3 facade fix e61accaf: onlythree scopedfiles, wrapperdeleted, six existing calls retargeted, one addedabsenceowner. Initial292setup errors from missing nestedbasetemp parent preserved;292P baseline afterdirectoryfix. RED1F, GREEN293P, mutation1F, restored293P/10completefiles. Meitner scopedre-review dispatched. Parent inspected entirefixdiff and freshcollect7984; post-facade-accounting.json proves no droppedIDs, changedtestfiles whollyrerun,293rerun+7691unchangedfullrun IDs. Combined7972P/12S explicitly notwhole-suiteonfinalhead. Postcensus retains1097read/4324rows/3387uncertainties/197newcandidateIDs/32reductions. Newuncertainties266 vs264 solelytwounchangedSQLsites shifted234/393->229/388; rawreports preserved. No productionretry or userreply.

Task3: complete, fixround1/5 addresses P2, no openfinding. Meitner independentartifact/ASTreview PASS/PASS; report archived. BothTask3worker/reviewerclosed. Parent evidencecommit3591f3f2 recordsdocs/results. Stagingcaught contextpatchblankline whitespace (legitimate patchbytes), so compressedthatoneartifactlosslessly insteadofstrippingcontext. Theexisting *.log.* ignore rule required explicit force-add of thisplan's syntheticloggzip artifacts; no ignore/globalpolicychange.

Final review Tesla01a08c40-054c-7a70-8166-a90e9de31941 of6ba563d9..46ec6f31: no Critical/Important or source integration blocker. SourceTasks2/3 PASS, qualityAPPROVED, actualinventoryINCOMPLETE. OneP3: parent incorrectlyassigned scannerSQLfollow-up toC21, alreadydeferred SAnewsdensity. One docs-onlyfixwave dispatched toEinstein01a08c4a-5276-7952-aa45-32917a251e98 withfourfilebrief: separate CENSUS-SQL-001 maintenanceowner; rawcensus/source/testunchanged. Finalreviewandbrief archived. No secondwhole-suite/model/production activity.

Finaldocsfixc2d4dce9 changesexactfourdocs, establishes CENSUS-SQL-001 whileC21remainsSAnewsdensity. Parent gitdiff-check andruntime-equalitychecks pass; one scopedTeslare-reviewrequested. Worker report discloses per-command disablinghooks/signing; parent verifiedbothconfigkeysunset andhookdirectorycontainsonly.samplefiles. No configchanged or activehookidentified; workerinstructednottooverridecommitdefaultswithoutactualblocker. Originalcommit/reportpreserved, no historyrewrite. Finalsourceheadstill e61accaf.

Task4: complete forsourcecheckpoint. TeslaP3scopedre-reviewADDRESSED/specPASS/qualityPASS, no newbreakage; source/rawmeasurements/C21verifiedunchanged. Finalreview, onefixreportandscopedre-reviewarchived. Bothfinalagentsclosed. Task1actualinventory remainsincompletependingnarrowWAL/SHMcoordinationandread-retryauthorization; no countmanifest or production disposition. Preserve thisignoredscratchhandoff and linkedbranch; do not invoke integration/menu/cleanup as though thewholeplanwerecomplete. Master30bb31c7 unchanged, twooriginaluntrackednames retained unread.

Final archive commit c1b6a0be; nine commits since6ba563d9. Trackedworktreeclean; fullrange gitdiff-check passes; runtime/tests/apps/dependencies byte-identical toe61accaf. Master30bb31c7 reverifiedunchanged. All worker/reviewer agents closed, verification sessions finished. Next user approval requested only for necessary two-store SQLite WAL/SHM coordination and one renewed statistics-only read; no implied merge, provider or disposal approval.

September11 resumption: user authorizes necessary WAL/SHM creation/updates and warns not to adopt Opus's unapproved read/causal explanation blindly. Existing source tasks are not repeated. Installed interpreter reports SQLite3.37.2. Read primary SQLite WAL documentation and tagged sqlite/sqlite version-3.37.2 wal.c/os_unix.c/pager.c. Mainfile O_RDONLY plus exclusive-lock requirement makes the reported checkpoint attribution unproven; no prior logical before/after snapshot is available to prove no row changes. App concurrency is a confounder, not proof the App caused it either.

Ruling: retain kernel read-only mounts on main files and unrelated existing entries. Only the real DB parent needs namespace creation permission so SQLite can create/open its real shared sidecars under normal locking. This is not an exact-basename kernel sandbox; fixed SHA-bound inspector, stdlib-only isolated Python, query_only/authorizer, clean environment, net/PID isolation and payload-free syscall trace define the actual operation. No manual sidecar management or private WAL/SHM bind copies, no backup, no logical/mainfile writes. Cost if wrong: refuse this caller before production; do not silently widen permissions or claim its directory is entirely read-only.

Synthetic new RED initial9F1P: eight intended missing-caller assertions, one fixture used unqualified count(*) and was denied by the existing authorizer. Qualifying main.table as the approved inspector already does fixes the fixture, not policy/query. CorrectedRED8F2P. FirstGREEN30P includes prior20 plus tennewcontrols. Plainmode=ro closedWAL and crashretainedWAL both preserve mainbytes/mtime; crashWAL additionally preserves committedWALbytes while returning the newly committedrow. These controls do not reconstruct Opus's production activity.

Independent bounded boundary review delegated to Hubble01a08c73-25b2-7d00-a258-5370bd4df082, no production access or edits. Parent owns harness/tests/docs. Additional trace/nonwritable-preflight/concurrent writer controls in progress. Query SHA unchanged f851057861c55980d4aeb114a8cf230ca7203ad1f3f2d86ca905004f833627c5. No second production attempt yet.

Boundary first33P includes trace privacy, protected-main preflight and live writer commit while reader remains on its older snapshot. Synthetic copy mutation removes per-entry read-only binds: four named tests fail (both mainfiles, unrelated sibling, nested file); outside-directory positivecontrol stillpasses. Realcaller unchanged bymutation. First review accepts practicalshared-directory boundary, finds P1hardlink alias and P1loaderbytecache mismatch. Parent reproducesfiveREDs including actually executed forgedtimestamp-pyc; fixes nlink==1/identity uniqueness and compile exactverifiedsourcebytes. GREEN38P/0skip. Caller SHA8e11b37f1dd7d2d46242c3c5ef27ca93e1262eba8c2c1496299394f2fcbf7a90. Added descriptor/mapping lifecycle syscalls without tracebuffers. Exactone-time launcher pinscallerhash and creates separate renewedtrace/result/receipt with pendingtraceacceptance. ScopedHubble re-reviewrequestedbeforeproduction. No production invocation yet.

Hubble scopedpre-read acceptance: pinnedcaller/dispatcher accepted, no additionalpre-readblocker, cleanENV/-I-S-B/oneinvocation/mandatoryposttraceconditions. Exactdispatcher7265952d8881106d03daae7f65ba667237ac2a2f7321b67eb25a4ec4d9f5b722. Actualrenewal2026-09-10T18:05:28Zexit0; parentobserved mainmetadataexactlyequal, mainFDs3/4O_RDONLY, closelocksbothEBADF. Datafilewritecalls: twoSHMtruncates+sixteen1bytepwrites+two32KiBsharedRWmaps; WALopenedbutnotwritten, nounlink/rename. Outpute44cec4f6ba8fa2ab45dfc8d74083886835324c84e83feccb7582e440479baf8, tracefa54782fd24a136964ea4557cc811df60a5dd4cb02b5924c0bba8447cf140391. Acceptedcounts are observationonly, notDROPauthorization. Hubbleposttracereviewpending; no secondrenewedquery.

Resultmanifest: profile29namedtablesobserved/8absent, market2observed. Sevenoldwebtablesabsentplusdisposalreceiptabsent.36SECobservationsand37kindrows;36matchedSECcases/setdiff0,39totalcaseswith3listing.14SECcaseshaveassessments;17totalassessments9accepted3human(notpartitionedbysource).4historicaltranslations,3transitions,105memberships/105bindings/108events/3removed. Exactoldschedulekeys0/0, source-specificschedulerruntime1/jobhistory1.31profile+1marketdeclaredFKgroupsallmeasurable0orphans0externalchildgroups; noapp-levelclosureclaim. Newretentionmanifestdistinguishesabsenttablesfromrawunavailableclassifiers. Source/tests/apps/depsunchanged; master30bb31c7withoriginaltwountrackednamesunread. Archivedrawresult/receipt,compressedtrace/XML,andnonexecutablecaller/test/dispatchtext. Archivehashes/XMLcountsindependentlycheckedbyparent; no schema/prices/news/SA/privateconfigurationchanges.

FinalHubbleposttraceverdictACCEPT; reviewedall2515lines/descriptorandmappinglifecycles, scratchhashes,counts,manifestanddocs. No remaining safetyblocker; bothP1sacceptedfixed. P3staleP0-Erow independentlyconfirmedbyparentandcorrected, no artifactruntimechange. Parent rules this one-line statusfix requires exactdiff/consistencycheck, not another fullreviewloop. Reviewerclosed. Currentplan'sfourtaskscompletewithinboundedscopes; widercleanup/newSEC/productiondispositionstillopen. Preservebranch/worktreewithoutintegration. Copyledgerintoevidenceafterfinalverificationandremoveonlythisplan'sownignoredscratch; no siblingworkspaceororiginaluseruntrackedfilecleanup.

Finalfreshverification38P/0skip in2.37s, archivedwal-final-verified.xml.gz. Query/caller/dispatcherhashesunchanged; result/tracearchivehashesverified; gitdiff-checkclean. No src/tests/apps/data_sources/requirements difference fromc1b6a0be. The ledger and evidence are ready for a docs-only local commit; the entire development branch remainsunmergedandunpublished. Finalworking-scratch cleanup is limited to this exact plan directory afterarchival, with originalsourceclosure/testreports already stored in its evidence directory.
