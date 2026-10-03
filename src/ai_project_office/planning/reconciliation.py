"""Source-versus-independent comparisons, never proof of P6 equivalence."""
from .models import Schedule
from .calendar_cpm import CalendarCPMResult

def reconcile_p6(schedule: Schedule, calculation: CalendarCPMResult, *,
                 date_tolerance_hours: float = 1.0, float_tolerance_hours: float = 1.0) -> list[dict]:
    if date_tolerance_hours<0 or float_tolerance_hours<0: raise ValueError('Negative tolerance')
    rows=[]
    for aid,a in schedule.activities.items():
        source=a.metadata.get('source',{})
        from .parsers.xer import _date
        start=_date(source.get('early_start_date'))
        finish=_date(source.get('early_end_date'))
        independent=calculation.activities.get(aid)
        tf=a.metadata.get('total_float_hours')
        row={'activity_id':aid,'source_start':start,'source_finish':finish,'source_float_hours':tf,
             'source_critical': None if tf is None else tf<=0,
             'classification':'CALCULATION NOT COMPARABLE','likely_reasons':[]}
        if independent:
            row.update(independent_start=independent.start,independent_finish=independent.finish,
                       independent_float_hours=independent.total_float_hours,independent_critical=independent.critical)
        if independent and start and finish and tf is not None:
            ds=(independent.start-start).total_seconds()/3600
            df=(independent.finish-finish).total_seconds()/3600
            dtf=independent.total_float_hours-tf
            row.update(start_difference_hours=ds,finish_difference_hours=df,float_difference_hours=dtf)
            maximum=max(abs(ds),abs(df),abs(dtf))
            row['classification']='MATCH' if maximum<1e-6 else ('MINOR DIFFERENCE' if abs(ds)<=date_tolerance_hours and abs(df)<=date_tolerance_hours and abs(dtf)<=float_tolerance_hours else 'MATERIAL DIFFERENCE')
            if row['classification']=='MATERIAL DIFFERENCE':
                row['likely_reasons']=['Review P6 scheduling options, lag calendar policy, project finish basis and calendar definitions; neither engine is presumed correct.']
        else:
            row['likely_reasons']=['Source early dates/float or independent result unavailable; target dates are not substituted for scheduled dates.']
        rows.append(row)
    return rows
