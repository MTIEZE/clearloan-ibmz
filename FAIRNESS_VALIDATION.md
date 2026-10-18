# Fairness Validation Snapshot

Date: 18 October 2026
Environment: ClearLoan LinuxONE demo application
Model: scorecard-1.3
Status: Preliminary monitoring, not an independent fairness certification.

## Live results

The application database contained 50 applications at the time of measurement.
Overall approval rate was 48%. Reported average recorded decision latency was 3 ms.

| Audit group | Applications | Approval rate | Mean risk score |
|---|---:|---:|---:|
| Men | 19 | 58% | 45.7 |
| Women | 26 | 38% | 53.7 |
| Not disclosed | 5 | 60% | 39.8 |

The observed men-women approval gap was 20 percentage points.
The undisclosed group had fewer than the minimum 10 applications and is
excluded from group-gap calculations.

## Age-group results

| Age band | Applications | Approval rate | Eligible for ratio |
|---|---:|---:|---|
| 18 to 25 | 4 | 25% | No; below minimum group size |
| 26 to 35 | 11 | 45% | Yes |
| 36 to 50 | 21 | 52% | Yes |
| 51 and over | 14 | 50% | Yes |

The reported age-group ratio was 0.87, based on eligible groups.

## Follow-up analysis

| Indicator | Men | Women |
|---|---:|---:|
| Average payment-to-bill ratio | 0.45 | 0.36 |
| Average loan size in months of bills | 8.36 | 7.06 |
| Applicants without credit history | 32% | 38% |
| Average late payments | 1.37 | 1.31 |

Mean score contributions were:
- Payment ratio: men -0.414; women -0.032.
- Loan amount: men +0.025; women -0.066.
- Repayment record: men +0.935; women +1.059.
- Education: men -0.016; women +0.017.

Repayment-record contributions apply only to applicants with credit history.
The credit-history contribution applies only to applicants without it; these
conditional means must not be interpreted as contributions across every member
of each group.

## Interpretation and limitations

Sex is not passed directly to the current score function. However, financial
inputs may correlate with sex, so omitting sex alone does not establish fairness.
The payment-ratio distribution and contributions are a possible explanation for
part of the observed gap, not proof of its cause.

These are a small, evolving demo-database snapshot, not representative borrower
evidence or proof of fairness. The observed 20-percentage-point gap warrants
further investigation using larger, appropriately labelled data and additional
group and error-rate analysis. Do not describe the model as independently
fairness-validated based on this snapshot.
