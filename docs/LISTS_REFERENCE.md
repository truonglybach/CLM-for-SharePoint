# CLM SharePoint List - Column Reference (v2)

The query layer behind all analytics. provision_lists.py creates these idempotently. Power BI and Power Automate read these typed columns directly; the orchestrator upserts rows keyed by the Key column. Only rows with ReviewStatus = Approved should feed dashboards and comparisons. Rows where PriorityReview = True should be triaged before other Pending rows.

## Contract Index - one row per contract

Columns: ContractID, Title, Counterparty, ContractType, Status, EffectiveDate, ExpirationDate, CurrentValue, FundingSource, ReviewStatus, PriorityReview.

## Amendment Index - one row per amendment

Columns: AmendmentID, ContractID, AmendmentNumber, AmendmentType, EffectiveDate, ValueChange, ReviewStatus.

## Clause Map Index - one row per clause<->term mapping

Columns: MapID, ContractID, ClauseID, TermID, RelevanceScore, ExtractionConfidence, ReviewStatus, PriorityReview.

## Subject Matter Terms - taxonomy source, one row per term

Columns: TermID, Domain, TermName, Definition, Synonyms (semicolon-separated), RegulatorySource.

Not an index list: the orchestrator reads it as the candidate-term taxonomy for clause mapping. Without rows here the real AI backend abstains on every clause, so no Clause Map Index rows are produced.

Notes: Choice columns give clean filters/slicers in Power BI without lookups. ContractID as foreign key lets Power BI relate the three Lists for cross-contract clause-coverage analytics. For datasets beyond a few thousand rows, index key + ReviewStatus + PriorityReview columns in List settings.
