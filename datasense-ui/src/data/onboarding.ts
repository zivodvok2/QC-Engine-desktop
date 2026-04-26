export interface OnboardingStep {
  id: string
  title: string
  body: string
  icon: string
}

export const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to Servallab',
    body: 'Servallab is a precision survey quality control tool. Upload a CSV or Excel file to get started — it will automatically detect issues in your data and give you a structured report.',
    icon: '👋',
  },
  {
    id: 'upload',
    title: 'Upload your data',
    body: 'Use the sidebar to upload a CSV or Excel file. Servallab accepts .csv, .xlsx, and .xls formats. Once uploaded, your columns appear in each tab for configuration.',
    icon: '📂',
  },
  {
    id: 'columns',
    title: 'Select columns for each check',
    body: 'Once data is loaded, click column chips to assign them to checks — in Logic, Straightlining, and EDA tabs. No drag-and-drop required.',
    icon: '↔️',
  },
  {
    id: 'qc_tab',
    title: 'QC Report tab',
    body: 'This tab shows all issues found in your data, grouped by severity — Critical, Warning, and Info. Expand any issue to see the flagged rows and download the Excel report.',
    icon: '🔍',
  },
  {
    id: 'logic_tab',
    title: 'Logic Checks tab',
    body: "Define conditional rules: 'If column A meets a condition, column B should meet another.' Build rules with the visual builder then run them against your file.",
    icon: '🔗',
  },
  {
    id: 'straightlining_tab',
    title: 'Straightlining tab',
    body: 'Select your base variable (e.g. interviewer ID) and question columns to detect respondents giving the same answer across all rating scale questions.',
    icon: '📋',
  },
  {
    id: 'eda_tab',
    title: 'EDA tab',
    body: 'Build custom charts with your columns. Choose from bar, line, scatter, histogram, heatmap, and box plots — powered by Recharts.',
    icon: '📊',
  },
  {
    id: 'export',
    title: 'Export your report',
    body: 'Click the Download Report button in the QC Report tab to get an Excel file with your QC flags, a severity breakdown, and interviewer analysis.',
    icon: '⬇️',
  },
]
