# Team Rooms

`room/v1` gives a Room one canonical identity, membership list and explicit
mode: Discuss, Execute or Review. Discuss is read/conversation oriented;
Execute may create Work Items and Review is a separate review flow.

Changing mode, mentioning a Bot, creating work or changing membership is a
Runtime operation. The Desktop renders the mode strip but disables it until
the Room contract and action descriptor are verified.
