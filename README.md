# TinkerBolus
**TinkerBolus is an interactive tool that shows the effect of alternate insulin timing on historical blood glucose.  It is intended as a conceptual visualization only and should not be used to make changes to insulin therapy.  These visualizations make several unreliable assumptions, in particular that the insulin model is correct and that ISF is known and is constant.**

To run TinkerBolus, download and run TinkerBolus.py as a Python script.  (The following screenshot is not interactive.)
![image](https://github.com/bedtime4bonzos/TinkerBolus/assets/6617751/18816d85-0481-4446-b61c-90f1056a741f)

Use the "Load!" button to load historical blood glucose, insulin, and carb data.

Insulin boluses are displayed as green markers.  Insulin amounts and timing can be modified in the following ways:
1. **Drag** and drop.
2. **Delete** by pressing  _'d'_  with the pointer over an insulin bolus.
3. **Insert** by pressing  _'i'_  with the pointer at the location to insert an insulin bolus.  The size of the inserted bolus is set in the "Bolus to Insert (U)" field.
4. (Advanced) Delete and **Accumulate** insulin by pressing  _'a'_  over an insulin bolus.  Insulin accumulated in this way will populate the "Bolus to Insert (U)" field for later insertion.  This is particularly helpful to combine many small boluses into a single bolus for easier manipulation.

The orange and green lines show the insulin effect and insulin counteraction effects.  This slider on the right adjusts the ISF used to compute these effects from the BG and insulin data.

The MongoDB URI is currently set in TinkerBolus.py if you'd like to use a URI other than the deault test URI provided.

Currently the only insulin model available in TinkerBolus is the Scalable Exponential Insulin Model discussed at <https://github.com/LoopKit/Loop/issues/388> with an activity peak of 75 minutes and a duration of 360 minutes (approximate model for Novolog).
